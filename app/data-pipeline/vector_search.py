"""
vector_search.py — retrieval utilities for the KSP Saathi RAG layer.

Two interchangeable vector stores. Both expose:

    .search(query_vector: list[float], top_k: int, filters: dict | None) -> list[Hit]

Hit fields: fir_no, score (cosine 0..1), text, crime_type, district, date.

Use LocalVectorStore for dev / unit tests / the embed_sample.py smoke test.
Use CatalystNosqlVectorStore from a Catalyst Function (rag-retriever) in prod.

Both stores load the full corpus into memory once and run cosine in NumPy.
At 50K × 768 floats = ~150 MB this fits comfortably in a Catalyst Function.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np

try:
    import zcatalyst_sdk  # type: ignore
    _HAS_CATALYST = True
except ImportError:
    _HAS_CATALYST = False


CATALYST_TABLE = "narrative_embeddings"


# ─── Result type ─────────────────────────────────────────────────────────────

@dataclass
class Hit:
    fir_no: str
    score: float
    text: str
    crime_type: str
    district: str
    date: str

    def to_dict(self) -> dict:
        return asdict(self)


class VectorStore(Protocol):
    def search(self, query_vector: list[float], top_k: int = 5,
               filters: dict | None = None) -> list[Hit]: ...


# ─── Shared helpers ──────────────────────────────────────────────────────────

def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def _l2_normalize_vec(vec: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(vec)
    return vec if n == 0 else vec / n


def _passes_filters(meta: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    for k, v in filters.items():
        if k not in meta:
            return False
        cell = meta[k]
        if isinstance(v, (list, tuple, set)):
            if cell not in v:
                return False
        elif isinstance(v, dict):
            # Range filters: {"gte": "2024-01-01", "lte": "2024-12-31"}
            gte, lte = v.get("gte"), v.get("lte")
            if gte is not None and cell < gte:
                return False
            if lte is not None and cell > lte:
                return False
        else:
            if cell != v:
                return False
    return True


# ─── Local JSONL store ───────────────────────────────────────────────────────

class LocalVectorStore:
    """
    Loads embeddings from a JSONL file (output of embed_narratives.py --output-mode local-json)
    and serves cosine-similarity search from memory.
    """

    def __init__(self, jsonl_path: str | os.PathLike):
        self.path = Path(jsonl_path)
        self._matrix: np.ndarray | None = None
        self._meta: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {self.path}")
        vectors: list[list[float]] = []
        meta: list[dict] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                vectors.append(row["embedding"])
                meta.append({
                    "fir_no": row["fir_no"],
                    "text": row.get("text", ""),
                    "crime_type": row.get("crime_type", ""),
                    "district": row.get("district", ""),
                    "date": row.get("date", ""),
                })
        if not vectors:
            raise RuntimeError(f"No embeddings found in {self.path}")
        self._matrix = _l2_normalize(np.asarray(vectors, dtype=np.float32))
        self._meta = meta

    def __len__(self) -> int:
        return len(self._meta)

    def search(self, query_vector: list[float], top_k: int = 5,
               filters: dict | None = None) -> list[Hit]:
        assert self._matrix is not None
        q = _l2_normalize_vec(np.asarray(query_vector, dtype=np.float32))
        scores = self._matrix @ q  # cosine because both sides are L2-normed

        # Apply filters by masking scores
        if filters:
            mask = np.array(
                [_passes_filters(m, filters) for m in self._meta],
                dtype=bool,
            )
            scores = np.where(mask, scores, -np.inf)

        k = min(top_k, len(self._meta))
        if k == 0:
            return []
        # Partial top-k via argpartition then sort that slice
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        hits: list[Hit] = []
        for i in idx:
            s = float(scores[i])
            if not np.isfinite(s):
                continue
            m = self._meta[i]
            hits.append(Hit(
                fir_no=m["fir_no"],
                score=s,
                text=m["text"],
                crime_type=m["crime_type"],
                district=m["district"],
                date=m["date"],
            ))
        return hits


# ─── Catalyst NoSQL store ────────────────────────────────────────────────────

class CatalystNosqlVectorStore:
    """
    Loads embeddings from Catalyst NoSQL table `narrative_embeddings` once at
    construction, then serves cosine search from memory. Acceptable for ≤50K rows.

    For Catalyst Function usage: construct once at module load (cold-start), then
    call .search() per request. Memory footprint ≈ 150 MB at 768 dims.
    """

    def __init__(self, table: str = CATALYST_TABLE, app=None):
        if not _HAS_CATALYST:
            raise RuntimeError("zcatalyst-sdk not installed — pip install zcatalyst-sdk")
        self.table_name = table
        if app is None:
            try:
                self.app = zcatalyst_sdk.initialize()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "Catalyst initialise failed. Inside a Function pass "
                    "zcatalyst_sdk.initialize(context); locally set CATALYST_* env."
                ) from exc
        else:
            self.app = app
        self._matrix: np.ndarray | None = None
        self._meta: list[dict] = []
        self._load()

    def _iter_rows(self) -> Iterable[dict]:
        ds = self.app.datastore()
        table = ds.table(self.table_name)
        page = 1
        while True:
            try:
                rows = table.get_paged_rows(page=page, per_page=200)
            except Exception:  # noqa: BLE001
                break
            items = rows.get("data", []) if isinstance(rows, dict) else rows
            if not items:
                break
            for r in items:
                yield r
            if len(items) < 200:
                break
            page += 1

    def _load(self) -> None:
        vectors: list[list[float]] = []
        meta: list[dict] = []
        for row in self._iter_rows():
            emb = row.get("embedding")
            if not emb:
                continue
            if isinstance(emb, str):  # JSON-encoded array fallback
                try:
                    emb = json.loads(emb)
                except json.JSONDecodeError:
                    continue
            vectors.append(emb)
            meta.append({
                "fir_no": row.get("fir_no", ""),
                "text": row.get("text", ""),
                "crime_type": row.get("crime_type", ""),
                "district": row.get("district", ""),
                "date": row.get("date", ""),
            })
        if not vectors:
            raise RuntimeError(f"No embeddings found in Catalyst NoSQL table `{self.table_name}`")
        self._matrix = _l2_normalize(np.asarray(vectors, dtype=np.float32))
        self._meta = meta

    def __len__(self) -> int:
        return len(self._meta)

    def search(self, query_vector: list[float], top_k: int = 5,
               filters: dict | None = None) -> list[Hit]:
        # Identical cosine-search logic as the local store.
        assert self._matrix is not None
        q = _l2_normalize_vec(np.asarray(query_vector, dtype=np.float32))
        scores = self._matrix @ q
        if filters:
            mask = np.array(
                [_passes_filters(m, filters) for m in self._meta],
                dtype=bool,
            )
            scores = np.where(mask, scores, -np.inf)
        k = min(top_k, len(self._meta))
        if k == 0:
            return []
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        hits: list[Hit] = []
        for i in idx:
            s = float(scores[i])
            if not np.isfinite(s):
                continue
            m = self._meta[i]
            hits.append(Hit(
                fir_no=m["fir_no"],
                score=s,
                text=m["text"],
                crime_type=m["crime_type"],
                district=m["district"],
                date=m["date"],
            ))
        return hits


# ─── Query embedding helper (RETRIEVAL_QUERY task type) ──────────────────────

def embed_query(text: str, api_key: str | None = None, dim: int = 768) -> list[float]:
    """
    Embed a user's live query with task_type=RETRIEVAL_QUERY (asymmetric to
    RETRIEVAL_DOCUMENT used at ingest). L2-normalised for direct cosine.
    """
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=genai_types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=dim,
        ),
    )
    vec = np.asarray(result.embeddings[0].values, dtype=np.float32)
    n = np.linalg.norm(vec)
    return (vec / n).tolist() if n else vec.tolist()
