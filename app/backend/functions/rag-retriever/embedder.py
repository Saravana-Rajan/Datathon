"""Embedding helpers for the RAG retriever Catalyst Function.

Thin, ingestion-friendly wrapper around `gemini-embedding-001` that exposes:

  * `embed_query(text)`       — single-shot RETRIEVAL_QUERY embedding
  * `embed_batch(texts)`      — batched RETRIEVAL_DOCUMENT embeddings
                                (used by `app/data-pipeline/embed_narratives.py`
                                and the retriever's own runtime fallback)
  * `cosine_similarity(a, b)` — pure-Python cosine, kept here so the retriever
                                and the ingestion script use the same math.

Retries are handled by the shared GeminiClient (`_with_retry_sync`) — we
just choose the task_type and re-export numpy-free helpers.

Why this lives next to `index.py` (and not in `shared/`):
    Catalyst Functions are zip-packaged per directory. Importing from a
    sibling `shared/` works only after Catalyst's `dependencies` feature
    flattens it into the bundle. Co-locating the helper keeps the cold-
    start surface small and the test loop fast.
"""

from __future__ import annotations

import logging
import math
import os
import sys
import time
from typing import Iterable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resolve the shared gemini client. We try the package-style import first
# (works in deployed bundles where `shared/` is co-vendored), then fall back
# to a sys.path injection for local pytest runs.
# ---------------------------------------------------------------------------

_SHARED_GEMINI = None


def _shared_gemini():
    """Lazy-load the shared gemini client to keep cold start cheap."""
    global _SHARED_GEMINI
    if _SHARED_GEMINI is not None:
        return _SHARED_GEMINI

    try:
        from shared import gemini_client as _gc  # type: ignore
    except ImportError:
        # Local-dev fallback: add backend/ to sys.path then retry.
        here = os.path.dirname(os.path.abspath(__file__))
        backend_root = os.path.abspath(os.path.join(here, "..", ".."))
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        try:
            from shared import gemini_client as _gc  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "shared.gemini_client not importable. "
                "Ensure backend/shared/ is on sys.path or bundled in the function."
            ) from exc

    _SHARED_GEMINI = _gc
    return _SHARED_GEMINI


# ---------------------------------------------------------------------------
# Tunables (env-overridable so eval scripts can pin model versions)
# ---------------------------------------------------------------------------

EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))
EMBED_DIM_FALLBACK = int(os.getenv("EMBED_DIM_FALLBACK", "3072"))  # gemini-embedding-001 native dim

# Embedder-level retry knobs. The shared client already retries inside, but
# we wrap calls with a coarser outer loop so partial batch failures during
# ingestion can resume without dropping the whole batch.
OUTER_RETRIES = int(os.getenv("EMBED_OUTER_RETRIES", "2"))
OUTER_BACKOFF_S = float(os.getenv("EMBED_OUTER_BACKOFF_S", "1.0"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_query(text: str) -> list[float]:
    """Embed a single user query using RETRIEVAL_QUERY task type.

    Returns a list[float] of length ~EMBED_DIM_FALLBACK. Empty input returns
    an empty vector (callers should treat that as "skip retrieval").
    """
    if not text or not text.strip():
        return []
    gc = _shared_gemini()
    client = gc.get_embedding_client(EMBED_MODEL)
    vectors = _outer_retry(
        lambda: client.embed([text.strip()], task_type="RETRIEVAL_QUERY"),
        label=f"embed_query(len={len(text)})",
    )
    return vectors[0] if vectors else []


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of narratives using RETRIEVAL_DOCUMENT task type.

    Splits the input into `EMBED_BATCH_SIZE` chunks so we never blow past
    the Gemini batch-content limit. Preserves input order; empty strings
    in the input become empty vectors in the output (so the caller's
    list[fir_no] zip stays aligned).
    """
    if not texts:
        return []

    gc = _shared_gemini()
    client = gc.get_embedding_client(EMBED_MODEL)

    out: list[list[float]] = [[] for _ in texts]

    # Build dense sub-batches: skip empty entries but remember their slots.
    non_empty: list[tuple[int, str]] = [(i, t.strip()) for i, t in enumerate(texts) if t and t.strip()]
    if not non_empty:
        return out

    for start in range(0, len(non_empty), EMBED_BATCH_SIZE):
        chunk = non_empty[start : start + EMBED_BATCH_SIZE]
        chunk_texts = [t for _, t in chunk]
        vectors = _outer_retry(
            lambda chunk_texts=chunk_texts: client.embed(
                chunk_texts, task_type="RETRIEVAL_DOCUMENT"
            ),
            label=f"embed_batch chunk={start}:{start + len(chunk)}",
        )
        for (slot, _), vec in zip(chunk, vectors):
            out[slot] = vec
    return out


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors.

    Returns 0.0 if either vector is empty or zero-norm — that's the safe
    "no match" signal a caller can sort on without special-casing.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def cosine_similarity_many(query: list[float], corpus: Iterable[list[float]]) -> list[float]:
    """Score a query against every vector in `corpus` (preserved order)."""
    return [cosine_similarity(query, vec) for vec in corpus]


# ---------------------------------------------------------------------------
# Internal: outer retry wrapper (the shared client already has an inner one;
# this catches "the whole batch call blew up" failures during ingestion).
# ---------------------------------------------------------------------------

def _outer_retry(fn, *, label: str):
    last_exc: Exception | None = None
    for attempt in range(OUTER_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — propagate after final attempt
            last_exc = exc
            if attempt >= OUTER_RETRIES:
                break
            wait = OUTER_BACKOFF_S * (2 ** attempt)
            logger.warning(
                "embedder outer retry %d/%d for %s: %s (wait %.2fs)",
                attempt + 1, OUTER_RETRIES, label, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"embedder failed after {OUTER_RETRIES + 1} attempts ({label}): {last_exc}")
