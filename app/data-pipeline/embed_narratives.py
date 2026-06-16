"""
embed_narratives.py — Gemini embeddings batch ingestion for KSP Saathi RAG layer.

Embeds the 50K synthetic FIR narratives (English + Kannada combined) using
`gemini-embedding-001` with task_type=RETRIEVAL_DOCUMENT and writes them to
either Catalyst NoSQL (production target) or a local JSONL file (dev/testing).

USAGE
-----
    # Dev: write to local JSONL for testing
    python embed_narratives.py --input ../../data/firs.jsonl \\
        --output-mode local-json --batch 100

    # Production: write to Catalyst NoSQL
    python embed_narratives.py --input ../../data/firs.jsonl \\
        --output-mode catalyst-nosql --batch 100 --resume

    # Both (mirror to local for inspection while populating prod)
    python embed_narratives.py --input ../../data/firs.jsonl \\
        --output-mode both --batch 100 --resume

ENV
---
    GEMINI_API_KEY            (required)
    CATALYST_PROJECT_ID       (required only for catalyst-nosql)
    CATALYST_TOKEN            (required only for catalyst-nosql — API key / OAuth token)
    CATALYST_DOMAIN           default: https://api.catalyst.zoho.in

OUTPUT SCHEMA (both modes)
--------------------------
    {
      "fir_no":      str,
      "embedding":   list[float],   # length = DIM (default 768)
      "text":        str,           # the narrative chunk that was embedded
      "crime_type":  str,
      "district":    str,
      "date":        str,           # YYYY-MM-DD
      "lang":        "bilingual",
      "task_type":   "RETRIEVAL_DOCUMENT",
      "model":       "gemini-embedding-001",
      "dim":         768
    }

NOTES
-----
- Idempotent: --resume reads destination, skips fir_no already embedded.
- Rate-limit safe: exponential backoff on 429 / 503.
- Cost report printed every N batches.
- Catalyst writes happen in row-batches of 100 (NoSQL bulk insert limit).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
from tqdm import tqdm

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("ERROR: install google-genai  ->  pip install google-genai", file=sys.stderr)
    raise

# Catalyst SDK is optional — only required for catalyst-nosql mode
try:
    import zcatalyst_sdk  # type: ignore
    _HAS_CATALYST = True
except ImportError:
    _HAS_CATALYST = False


# ─── Configuration ───────────────────────────────────────────────────────────

MODEL = "gemini-embedding-001"
DIM = 768                          # Matryoshka — 4x cheaper storage than 3072
TASK_TYPE = "RETRIEVAL_DOCUMENT"
MAX_NARRATIVE_CHARS = 6000         # ~1500 tokens, well under 2048 cap
PRICE_PER_M_TOKENS = 0.15          # $/M tokens, standard API
CATALYST_TABLE = "narrative_embeddings"
DEFAULT_LOCAL_OUT = "embeddings.jsonl"
DEFAULT_CATALYST_DOMAIN = "https://api.catalyst.zoho.in"


# ─── Data shapes ─────────────────────────────────────────────────────────────

@dataclass
class FirRecord:
    fir_no: str
    crime_type: str
    district: str
    date: str
    location_text: str
    narrative_en: str
    narrative_kn: str

    def build_chunk(self) -> str:
        """Single bilingual chunk per FIR — header + EN + KN narrative."""
        header = (
            f"FIR: {self.fir_no} | Crime: {self.crime_type} | "
            f"District: {self.district} | Location: {self.location_text} | "
            f"Date: {self.date}"
        )
        text = f"{header}\n\nNARRATIVE (EN): {self.narrative_en}\n\nNARRATIVE (KN): {self.narrative_kn}"
        return text[:MAX_NARRATIVE_CHARS]


@dataclass
class EmbedRow:
    fir_no: str
    embedding: list[float]
    text: str
    crime_type: str
    district: str
    date: str

    def to_dict(self) -> dict:
        return {
            "fir_no": self.fir_no,
            "embedding": self.embedding,
            "text": self.text,
            "crime_type": self.crime_type,
            "district": self.district,
            "date": self.date,
            "lang": "bilingual",
            "task_type": TASK_TYPE,
            "model": MODEL,
            "dim": DIM,
        }


# ─── FIR JSONL loader ────────────────────────────────────────────────────────

def load_firs(path: Path) -> Iterator[FirRecord]:
    """Stream-load the FIR JSONL one record at a time."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            yield FirRecord(
                fir_no=obj["fir_no"],
                crime_type=obj.get("crime_type", "unknown"),
                district=obj.get("district", "unknown"),
                date=obj.get("date_registered", ""),
                location_text=obj.get("location_text", ""),
                narrative_en=obj.get("narrative", "") or "",
                narrative_kn=obj.get("narrative_kannada", "") or "",
            )


# ─── Gemini embedding call (with retry) ──────────────────────────────────────

class GeminiEmbedder:
    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.total_tokens = 0
        self.total_calls = 0

    def _normalize(self, vec: list[float]) -> list[float]:
        """L2-normalize — required for cosine when DIM != 3072."""
        arr = np.asarray(vec, dtype=np.float32)
        n = np.linalg.norm(arr)
        if n == 0:
            return vec
        return (arr / n).tolist()

    def embed_batch(self, texts: list[str], max_retries: int = 5) -> list[list[float]]:
        """Embed a list of texts in one API call. Retries on transient errors."""
        cfg = genai_types.EmbedContentConfig(
            task_type=TASK_TYPE,
            output_dimensionality=DIM,
        )
        attempt = 0
        while True:
            try:
                result = self.client.models.embed_content(
                    model=MODEL,
                    contents=texts,
                    config=cfg,
                )
                vectors = [self._normalize(e.values) for e in result.embeddings]
                # Approximate token usage: 1 token ≈ 4 chars
                est_tokens = sum(len(t) for t in texts) // 4
                self.total_tokens += est_tokens
                self.total_calls += 1
                return vectors
            except Exception as exc:  # noqa: BLE001
                attempt += 1
                if attempt > max_retries:
                    raise
                # Exponential backoff with jitter — handles 429 / 503 / network
                wait = min(60.0, (2 ** attempt) + random.uniform(0, 1))
                msg = str(exc)[:200]
                print(f"  [retry {attempt}/{max_retries}] {msg} — sleeping {wait:.1f}s", file=sys.stderr)
                time.sleep(wait)

    def cost_so_far(self) -> float:
        return (self.total_tokens / 1_000_000) * PRICE_PER_M_TOKENS


# ─── Destinations: local JSONL + Catalyst NoSQL ──────────────────────────────

class LocalJsonlSink:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._existing: set[str] = set()

    def existing_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        ids: set[str] = set()
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["fir_no"])
                except Exception:  # noqa: BLE001
                    continue
        self._existing = ids
        return ids

    def write(self, rows: list[EmbedRow]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


class CatalystNosqlSink:
    """
    Writes embeddings to Catalyst NoSQL table `narrative_embeddings`.

    Uses the zcatalyst-sdk-python SDK. Auth modes supported:
      * Inside Catalyst Function: zcatalyst_sdk.initialize(context) — handled by runtime
      * Local dev: pass CATALYST_PROJECT_ID + CATALYST_TOKEN env vars
    """

    def __init__(self, project_id: str | None = None, token: str | None = None,
                 table: str = CATALYST_TABLE, domain: str = DEFAULT_CATALYST_DOMAIN):
        if not _HAS_CATALYST:
            raise RuntimeError(
                "zcatalyst-sdk not installed — pip install zcatalyst-sdk\n"
                "(or use --output-mode local-json for testing)"
            )
        self.table_name = table
        # Local-dev initialisation pattern (Catalyst CLI / standalone script)
        env = {
            "X-ZOHO-CATALYST-ORG-ID": project_id or os.environ.get("CATALYST_PROJECT_ID", ""),
            "CATALYST_AUTH_TOKEN": token or os.environ.get("CATALYST_TOKEN", ""),
            "CATALYST_DOMAIN": domain,
        }
        if not env["X-ZOHO-CATALYST-ORG-ID"] or not env["CATALYST_AUTH_TOKEN"]:
            raise RuntimeError(
                "Catalyst credentials missing. Set CATALYST_PROJECT_ID and CATALYST_TOKEN, "
                "or run inside a Catalyst Function with zcatalyst_sdk.initialize(context)."
            )
        # The SDK auto-discovers env in some flows; we explicitly construct an app.
        try:
            self.app = zcatalyst_sdk.initialize()
        except Exception:  # noqa: BLE001
            # Fallback — some SDK versions require a context-like dict
            self.app = zcatalyst_sdk.initialize(env)
        self.datastore = self.app.datastore()
        self.table = self.datastore.table(self.table_name)

    def existing_ids(self) -> set[str]:
        """Scan all rows in the table — acceptable for ≤50K rows."""
        ids: set[str] = set()
        page = 1
        while True:
            try:
                rows = self.table.get_paged_rows(page=page, per_page=200)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: could not page table for resume scan: {exc}", file=sys.stderr)
                break
            items = rows.get("data", []) if isinstance(rows, dict) else rows
            if not items:
                break
            for r in items:
                if "fir_no" in r:
                    ids.add(r["fir_no"])
            if len(items) < 200:
                break
            page += 1
        return ids

    def write(self, rows: list[EmbedRow]) -> None:
        """Bulk-insert. Catalyst NoSQL accepts up to 100 rows per insert call."""
        if not rows:
            return
        payload = [r.to_dict() for r in rows]
        # SDK API varies slightly by version — try the two common names.
        try:
            self.table.insert_rows(payload)
        except AttributeError:
            self.table.insert_row(payload)


# ─── Batched ingestion driver ────────────────────────────────────────────────

def chunked(it: Iterable[FirRecord], size: int) -> Iterator[list[FirRecord]]:
    buf: list[FirRecord] = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def run(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    # ---- Set up destination sinks
    sinks: list[tuple[str, object]] = []
    skip_ids: set[str] = set()

    if args.output_mode in ("local-json", "both"):
        local = LocalJsonlSink(Path(args.local_out).resolve())
        sinks.append(("local-json", local))
        if args.resume:
            skip_ids |= local.existing_ids()
            print(f"  resume: {len(skip_ids)} fir_no already in local JSONL")

    if args.output_mode in ("catalyst-nosql", "both"):
        cat = CatalystNosqlSink(table=args.table)
        sinks.append(("catalyst-nosql", cat))
        if args.resume:
            cat_ids = cat.existing_ids()
            skip_ids |= cat_ids
            print(f"  resume: {len(cat_ids)} fir_no already in Catalyst NoSQL")

    if not sinks:
        print("ERROR: no output sinks selected", file=sys.stderr)
        return 2

    # ---- Embedder
    embedder = GeminiEmbedder(api_key=os.environ.get("GEMINI_API_KEY"))

    # ---- Stream + batch + embed
    total_estimate = args.limit if args.limit else 50_000
    pbar = tqdm(total=total_estimate, desc="Embedding FIRs", unit="fir")
    processed = 0
    written = 0

    batch_iter = chunked(load_firs(input_path), args.batch)
    cost_print_every = max(1, args.cost_print_every)
    batches_done = 0

    for batch in batch_iter:
        # Apply --limit (counts toward processed, not written)
        if args.limit and processed >= args.limit:
            break

        # Resume filter — skip already-embedded fir_no
        todo = [r for r in batch if r.fir_no not in skip_ids]
        skipped = len(batch) - len(todo)

        if todo:
            texts = [r.build_chunk() for r in todo]
            vectors = embedder.embed_batch(texts)

            rows = [
                EmbedRow(
                    fir_no=r.fir_no,
                    embedding=v,
                    text=t,
                    crime_type=r.crime_type,
                    district=r.district,
                    date=r.date,
                )
                for r, t, v in zip(todo, texts, vectors)
            ]
            for _name, sink in sinks:
                sink.write(rows)  # type: ignore[attr-defined]
            written += len(rows)

        processed += len(batch)
        pbar.update(len(batch))
        if skipped:
            pbar.set_postfix(skipped=skipped, written=written)

        batches_done += 1
        if batches_done % cost_print_every == 0:
            print(
                f"  [batch {batches_done}] calls={embedder.total_calls} "
                f"tokens≈{embedder.total_tokens:,} "
                f"cost≈${embedder.cost_so_far():.4f}",
                flush=True,
            )

    pbar.close()
    print(
        "\nDone. "
        f"processed={processed} written={written} "
        f"calls={embedder.total_calls} "
        f"tokens≈{embedder.total_tokens:,} "
        f"final_cost≈${embedder.cost_so_far():.4f}"
    )
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Embed KSP FIR narratives with Gemini.")
    p.add_argument("--input", required=True, help="Path to firs.jsonl")
    p.add_argument(
        "--output-mode",
        choices=["catalyst-nosql", "local-json", "both"],
        default="local-json",
        help="Where to write embeddings.",
    )
    p.add_argument("--local-out", default=DEFAULT_LOCAL_OUT,
                   help="Local JSONL path (used by local-json / both).")
    p.add_argument("--table", default=CATALYST_TABLE,
                   help="Catalyst NoSQL table name.")
    p.add_argument("--batch", type=int, default=100,
                   help="FIRs per Gemini API call (in-request batching).")
    p.add_argument("--limit", type=int, default=0,
                   help="Cap on FIRs to process (0 = all).")
    p.add_argument("--resume", action="store_true",
                   help="Skip fir_no already present in destination.")
    p.add_argument("--cost-print-every", type=int, default=10,
                   help="Print running cost every N batches.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run with --resume to continue.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
