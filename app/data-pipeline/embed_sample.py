"""
embed_sample.py — smoke test for the embeddings pipeline.

Runs end-to-end on the first 10 FIRs:
  1. Embeds them with RETRIEVAL_DOCUMENT.
  2. Embeds the query "vehicle theft near MG Road" with RETRIEVAL_QUERY.
  3. Computes cosine similarity, prints top-5.

This is the fastest way to verify your GEMINI_API_KEY works and that retrieval
quality is sensible BEFORE kicking off the full 50K ingestion.

USAGE
-----
    export GEMINI_API_KEY=...
    python embed_sample.py --input ../../data/firs_sample.jsonl
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from embed_narratives import (  # noqa: E402
    GeminiEmbedder, FirRecord, EmbedRow, LocalJsonlSink, load_firs,
)
from vector_search import LocalVectorStore, embed_query  # noqa: E402


DEFAULT_QUERY = "vehicle theft near MG Road"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Smoke-test embeddings pipeline.")
    p.add_argument("--input", default="../../data/firs_sample.jsonl",
                   help="Path to FIRs JSONL (sample is fine).")
    p.add_argument("--n", type=int, default=10,
                   help="Number of FIRs to embed for the smoke test.")
    p.add_argument("--query", default=DEFAULT_QUERY,
                   help="Test query to embed and run search against.")
    p.add_argument("--top-k", type=int, default=5)
    args = p.parse_args(argv)

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY env var not set.", file=sys.stderr)
        return 2

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 2

    print(f"[1/4] Loading first {args.n} FIRs from {input_path.name}")
    firs: list[FirRecord] = []
    for fr in load_firs(input_path):
        firs.append(fr)
        if len(firs) >= args.n:
            break
    print(f"      loaded {len(firs)} FIRs")

    # Embed documents
    print("[2/4] Embedding documents (RETRIEVAL_DOCUMENT)...")
    embedder = GeminiEmbedder()
    texts = [f.build_chunk() for f in firs]
    vectors = embedder.embed_batch(texts)
    print(f"      embedded {len(vectors)} docs; "
          f"dim={len(vectors[0])} tokens≈{embedder.total_tokens:,} "
          f"cost≈${embedder.cost_so_far():.6f}")

    # Persist to a temp JSONL and load via LocalVectorStore so we exercise the
    # exact same code path the RAG retriever uses.
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / "sample_embeddings.jsonl"
        sink = LocalJsonlSink(tmp_path)
        rows = [
            EmbedRow(
                fir_no=f.fir_no,
                embedding=v,
                text=t,
                crime_type=f.crime_type,
                district=f.district,
                date=f.date,
            )
            for f, t, v in zip(firs, texts, vectors)
        ]
        sink.write(rows)
        print(f"      wrote temp file: {tmp_path}")

        # Embed the query
        print(f"[3/4] Embedding query (RETRIEVAL_QUERY): {args.query!r}")
        q_vec = embed_query(args.query)

        # Search
        print(f"[4/4] Top-{args.top_k} by cosine similarity:")
        store = LocalVectorStore(tmp_path)
        hits = store.search(q_vec, top_k=args.top_k)

    if not hits:
        print("  (no hits — something is wrong)")
        return 1

    print()
    print(f"  {'#':<3} {'score':<8} {'fir_no':<22} {'crime_type':<18} {'district':<22} date")
    print(f"  {'-'*3} {'-'*8} {'-'*22} {'-'*18} {'-'*22} {'-'*10}")
    for i, h in enumerate(hits, 1):
        print(f"  {i:<3} {h.score:<8.4f} {h.fir_no:<22} {h.crime_type:<18} {h.district:<22} {h.date}")
    print()
    print("  Snippet of top hit:")
    snippet = hits[0].text.replace("\n", " ")[:240]
    print(f"    {snippet}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
