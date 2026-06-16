# Gemini Embeddings — Reference for KSP Saathi RAG

> Consolidated from official Google AI docs. Sources cited inline per section.
> Last fetched: 2026-06-16.

---

## 1. Why we use this

KSP Saathi is a conversational AI for Karnataka Police that needs to retrieve
relevant prior case narratives, FIR snippets, and SOPs at query time. The retrieval
corpus is **multilingual** — officer notes mix **Kannada** (script + romanized),
**English**, and occasional Hindi/Urdu code-switching.

Gemini embeddings serve two roles in our stack:

1. **Primary embedder** for the semantic-search layer over case narratives if we
   self-host the vector store (Catalyst NoSQL + cosine).
2. **Fallback embedder** if Zoho Catalyst QuickML's built-in RAG embedder shows
   weak Kannada recall during the eval phase (we will A/B against it — see §12).

Gemini was chosen over OpenAI/Cohere because (a) it has top-ranked MTEB Multilingual
scores, (b) free-tier text inputs for `gemini-embedding-001`, and (c) we already
have Gemini API keys provisioned for the chat/reasoning layer, so one less vendor.

---

## 2. Available Models

Source: <https://ai.google.dev/gemini-api/docs/embeddings>

| Model ID | Modalities | Max input | Output dims | Status |
|---|---|---|---|---|
| `gemini-embedding-001` | Text only | **2,048 tokens** | 128–3072 (recommend 768 / 1536 / 3072) | Stable (June 2025) |
| `gemini-embedding-2` | Text + image + audio + video + PDF | **8,192 tokens** | 128–3072 (recommend 768 / 1536 / 3072) | Stable (April 2026) |

Older `text-embedding-004` and `embedding-001` are not surfaced on the current
embeddings doc page — treat them as **deprecated for new builds**. [UNCERTAIN —
not formally announced as deprecated in the fetched pages, but absent from current model
lists.]

### Language coverage

Source: <https://developers.googleblog.com/en/gemini-embedding-available-gemini-api/>
and <https://ai.google.dev/gemini-api/docs/embeddings>.

- Official docs state **"over 100 languages"** for `gemini-embedding-001` and
  `gemini-embedding-2`.
- Gemini Embedding holds a **top spot on the MTEB Multilingual leaderboard**.
- **Kannada is not called out by name** in the fetched Google docs/blog. However,
  MTEB Multilingual evaluates on Indic-language tasks including Kannada
  (IndicCrosslingualSTS, IndicReviewsClusteringP2P, etc.), and a top-ranked model
  on that leaderboard necessarily handles Kannada with non-trivial quality.
  **[UNCERTAIN — confirmed via leaderboard semantics, not via an explicit "Kannada"
  string in the official doc.]** Our eval plan in §12 will measure this directly
  on KSP case narratives.

### Recommendation for KSP Saathi

Use **`gemini-embedding-001`** initially. Reasons:
- Text-only is sufficient (we ingest narratives as strings).
- Cheaper than `gemini-embedding-2` ($0.15 vs $0.20 per 1M tokens).
- Free-tier text inputs available during dev.
- Stable `task_type` parameter — `gemini-embedding-2` instead requires embedding
  task hints into the prompt, which complicates batched ingestion.

Reserve `gemini-embedding-2` for any future case-evidence images/audio.

---

## 3. Setup (Python SDK)

Source: <https://ai.google.dev/gemini-api/docs/embeddings>

```bash
pip install google-genai
export GEMINI_API_KEY="..."   # or pass api_key=... to Client()
```

Minimal first call:

```python
from google import genai

client = genai.Client()  # reads GEMINI_API_KEY from env

result = client.models.embed_content(
    model="gemini-embedding-001",
    contents="ಬೆಂಗಳೂರು ಕೋರಮಂಗಲದಲ್ಲಿ ವಾಹನ ಕಳ್ಳತನ ದೂರು ದಾಖಲಾಗಿದೆ.",
)
embedding = result.embeddings[0].values   # list[float], length 3072 by default
print(len(embedding))
```

For Catalyst/Zoho deployment: keep the API key in Catalyst Environment Variables,
not in code.

---

## 4. Task Types

Source: <https://ai.google.dev/api/embeddings> and
<https://ai.google.dev/gemini-api/docs/embeddings>.

Setting `task_type` materially changes the embedding — documents and queries get
projected into compatible-but-asymmetric subspaces optimized for retrieval. **Do
not skip this.**

| `task_type` | Use it for |
|---|---|
| `RETRIEVAL_DOCUMENT` | Embedding **stored** case narratives, FIRs, SOPs |
| `RETRIEVAL_QUERY` | Embedding the **officer's live question** at chat time |
| `SEMANTIC_SIMILARITY` | Symmetric similarity (e.g., deduping near-identical FIRs) |
| `CLASSIFICATION` | If we train a downstream classifier (case type, severity) |
| `CLUSTERING` | Grouping similar incidents for trend analysis |
| `QUESTION_ANSWERING` | Q-doc matching when query is phrased as a question |
| `FACT_VERIFICATION` | Evidence retrieval for a claim |
| `CODE_RETRIEVAL_QUERY` | Not used by us |

### KSP Saathi mapping

- **Ingestion** of every case narrative → `RETRIEVAL_DOCUMENT` (pass `title=` when
  we have a meaningful case title — it improves quality).
- **Query time** when an officer asks "ಬೈಕ್ ಕಳ್ಳತನ ಪ್ರಕರಣಗಳು" → `RETRIEVAL_QUERY`.
- **Dedup pipeline** comparing two FIRs → `SEMANTIC_SIMILARITY`.

Mixing `RETRIEVAL_DOCUMENT`-embedded vectors with `SEMANTIC_SIMILARITY`-embedded
ones in the same index will silently degrade results. Tag the `task_type` used
into each row at ingest.

---

## 5. Batching

Source: <https://ai.google.dev/api/embeddings>,
<https://ai.google.dev/gemini-api/docs/embeddings>.

Two batching modes:

1. **In-request list batching** — pass a list of strings to `contents=`. For
   `gemini-embedding-001` this returns **one embedding per item**. (For
   `gemini-embedding-2`, a list of inputs is *aggregated* into a single embedding
   — surprising footgun, see §10.)

   ```python
   result = client.models.embed_content(
       model="gemini-embedding-001",
       contents=["narrative 1...", "narrative 2...", "narrative 3..."],
       config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
   )
   # result.embeddings is a list of 3 ContentEmbedding
   ```

2. **Batch API** (`batchEmbedContents` / `asyncBatchEmbedContent`) — 50% cheaper,
   higher throughput, async. Use this for the one-shot ingestion of all historic
   KSP narratives.

   Endpoint: `POST .../v1beta/models/gemini-embedding-001:batchEmbedContents`

---

## 6. Pricing + Limits

Source: <https://ai.google.dev/gemini-api/docs/pricing>,
<https://ai.google.dev/gemini-api/docs/rate-limits>.

### `gemini-embedding-001` pricing

| Tier | Cost |
|---|---|
| Free tier | Text inputs at no charge (subject to free-tier RPM/TPM) |
| Paid standard | **$0.15 per 1M input tokens** |
| Paid batch API | **$0.075 per 1M input tokens** (50% off) |

### `gemini-embedding-2` pricing (text)

| Tier | Cost |
|---|---|
| Free tier | Free for text/image/audio/video |
| Paid standard | $0.20 per 1M tokens (text) |
| Paid batch | $0.10 per 1M tokens (text) |

### Rate limits

Google's public docs do **not list specific RPM/TPM** for embedding models —
they are tier-dependent and displayed live in AI Studio
(<https://aistudio.google.com/rate-limit>). **[UNCERTAIN — must be checked at
runtime per project.]**

Batch API enqueued-token caps (from the rate-limits doc):
- Tier 1: 500,000 tokens enqueued
- Tier 2: 5,000,000
- Tier 3: 10,000,000

### Token budget for KSP Saathi

Assuming ~50K narratives × ~400 tokens avg = **20M tokens** for full ingestion.
- Standard API: ~$3.00
- Batch API: ~$1.50

Effectively free.

### Max input

- `gemini-embedding-001`: **2,048 tokens** per call. Narratives over this must be
  **chunked**. Recommend ~1,500-token chunks with 200-token overlap.
- `gemini-embedding-2`: 8,192 tokens.

---

## 7. Output Dimensions

Source: <https://ai.google.dev/gemini-api/docs/embeddings>.

- Default: **3072 floats**.
- Configurable via `output_dimensionality` to any value in `[128, 3072]`.
  Recommended truncation points: **768, 1536, 3072** (these were trained with
  Matryoshka Representation Learning — they degrade gracefully).
- **Normalization**: 3072-dim outputs are pre-normalized. For
  `gemini-embedding-001`, **any non-3072 dim must be manually L2-normalized**
  before cosine similarity:

  ```python
  import numpy as np
  v = np.array(emb.values)
  v = v / np.linalg.norm(v)
  ```

  `gemini-embedding-2` auto-normalizes truncated dims.

For KSP Saathi: **start at 768 dims**. Storage in Catalyst NoSQL is 4×
cheaper than 3072, query latency drops, and MRL guarantees acceptable quality.
Re-evaluate at 1536 only if recall@10 on our eval set is unsatisfactory.

---

## 8. Storing in our system

Architectural options, ranked:

### Option A — Catalyst NoSQL + Python cosine (recommended for hackathon)
- Schema: `case_id` (string), `narrative` (text), `chunk_idx` (int),
  `embedding` (array<float> length 768), `task_type` (string),
  `embed_model_version` (string), `language` (string).
- At query time: load all embeddings into memory (50K × 768 × 4B = ~150 MB),
  compute cosine, return top-K. Fits comfortably in a single Catalyst Function.
- **Trade-off**: doesn't scale past ~500K vectors but is bulletproof for the demo.

### Option B — Catalyst QuickML RAG with external embeddings
- Only viable if QuickML accepts `bring-your-own-embedding`. **[UNCERTAIN — need to
  verify from QuickML docs.]** If it only accepts raw text and embeds internally,
  we lose the Gemini quality advantage.

### Option C — Vertex AI Vector Search / Pinecone / Qdrant
- Production-grade. Out of scope for the 36-hour hackathon but worth noting in
  the architecture deck.

**Index drift safety net**: store `embed_model_version="gemini-embedding-001"`
alongside every vector. If we ever switch to `gemini-embedding-2`, the spaces are
**incompatible** (see §10) and we MUST re-embed the whole corpus.

---

## 9. Code Recipes (copy-paste ready)

Source for all: <https://ai.google.dev/gemini-api/docs/embeddings>.

### Recipe A: Embed 50K case narratives in batches

```python
from google import genai
from google.genai import types
import numpy as np, json, time

client = genai.Client()
MODEL = "gemini-embedding-001"
DIM = 768
BATCH = 100  # in-request list batching

def normalize(vs):
    a = np.asarray(vs, dtype=np.float32)
    return (a / np.linalg.norm(a)).tolist()

def chunk(text, max_chars=6000):
    # ~1500 tokens. Adjust to taste; use tiktoken-like counters for precision.
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars - 800)]

def embed_documents(records, out_path):
    """records: iterable of dicts with 'case_id', 'title', 'narrative'."""
    with open(out_path, "w", encoding="utf-8") as f:
        buf = []
        for rec in records:
            for ci, ch in enumerate(chunk(rec["narrative"])):
                buf.append((rec["case_id"], ci, rec.get("title", ""), ch))
                if len(buf) >= BATCH:
                    flush(buf, f)
                    buf = []
        if buf:
            flush(buf, f)

def flush(buf, f):
    texts = [t for _, _, _, t in buf]
    # title= only takes one string; for batch we omit it. To use titles,
    # embed one-at-a-time when a title is present.
    while True:
        try:
            res = client.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=DIM,
                ),
            )
            break
        except Exception as e:
            print("retry:", e); time.sleep(5)
    for (case_id, ci, title, _), emb in zip(buf, res.embeddings):
        f.write(json.dumps({
            "case_id": case_id, "chunk_idx": ci, "title": title,
            "embedding": normalize(emb.values),
            "model": MODEL, "dim": DIM, "task_type": "RETRIEVAL_DOCUMENT",
        }, ensure_ascii=False) + "\n")
```

For the production 50K ingest, swap to the **Batch API** (50% cheaper).

### Recipe B: Query-time semantic search

```python
import numpy as np
from google import genai
from google.genai import types

client = genai.Client()

def embed_query(q, dim=768):
    res = client.models.embed_content(
        model="gemini-embedding-001",
        contents=q,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=dim,
        ),
    )
    v = np.asarray(res.embeddings[0].values, dtype=np.float32)
    return v / np.linalg.norm(v)

def topk(query, doc_matrix, doc_meta, k=10):
    """doc_matrix: (N, DIM) np.float32, L2-normalized."""
    q = embed_query(query)
    scores = doc_matrix @ q  # cosine since both normalized
    idx = np.argpartition(-scores, k)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [(doc_meta[i], float(scores[i])) for i in idx]

# Example
print(topk("ಬೈಕ್ ಕಳ್ಳತನ ಕೋರಮಂಗಲ", doc_matrix, doc_meta))
```

### Recipe C: Hybrid search (semantic + BM25)

```python
from rank_bm25 import BM25Okapi
import numpy as np

class HybridIndex:
    def __init__(self, docs, doc_matrix):
        # docs: list[str], doc_matrix: (N, DIM) L2-normalized np.float32
        self.docs = docs
        self.doc_matrix = doc_matrix
        # Tokenizer: simple whitespace works for Kannada+English mix; for
        # production swap to indic-nlp-library's tokenizer.
        self.bm25 = BM25Okapi([d.lower().split() for d in docs])

    def search(self, query, k=10, alpha=0.6):
        # alpha = weight of semantic; 1-alpha = weight of BM25
        sem = self.doc_matrix @ embed_query(query)  # cosine
        lex = np.asarray(self.bm25.get_scores(query.lower().split()),
                         dtype=np.float32)
        # Min-max normalize each signal before blending
        def norm(x):
            r = x.max() - x.min()
            return (x - x.min()) / r if r > 0 else x
        score = alpha * norm(sem) + (1 - alpha) * norm(lex)
        idx = np.argsort(-score)[:k]
        return [(self.docs[i], float(score[i])) for i in idx]
```

BM25 catches exact Kannada place-names and FIR numbers that embeddings sometimes
soften; semantic catches paraphrases. Start at `alpha=0.6`, tune on eval set.

---

## 10. Gotchas

1. **`gemini-embedding-2` aggregates list inputs.** Passing `contents=[a, b, c]`
   returns **one** embedding, not three. For per-document embeddings on v2 you
   must wrap each in a `types.Content(...)`. On `gemini-embedding-001` a list
   returns one-per-item as expected. (Source: §"Key Differences" in embeddings
   doc.)
2. **Embedding spaces of v001 and v2 are incompatible.** Mixing them in one
   index will produce nonsense rankings. Tag every stored vector with its model.
3. **Non-3072 dims on v001 are not normalized.** Always L2-normalize before
   cosine, or your scores will reflect magnitude noise.
4. **`task_type` mismatch silently degrades retrieval.** Always
   `RETRIEVAL_DOCUMENT` on ingest, `RETRIEVAL_QUERY` on lookup. Don't mix.
5. **2048-token cap on v001 is small.** Long FIR narratives must be chunked.
   `autoTruncate=True` exists but it silently drops content — prefer explicit
   chunking so we know what's indexed.
6. **Kannada coverage is empirically strong on MTEB but not officially named.**
   We MUST run our own retrieval eval on a held-out set of KSP Kannada queries
   before committing. See §12.
7. **Free-tier rate limits are not publicly fixed.** Check AI Studio for your
   project's live caps. Add exponential backoff in production code.
8. **Title field only helps `RETRIEVAL_DOCUMENT`.** Don't pass it for queries.
9. **Caching**: Gemini embed_content has no server-side prompt caching (that's
   a generation-model feature). For dedup-heavy ingestion, hash the chunk text
   and cache embeddings client-side.
10. **Index drift on model upgrade**: Google has already shipped v1 → v2 with
    incompatible spaces. Plan a re-embed budget for each upgrade.

---

## 11. India Region Considerations

Source: general Google AI docs; specifics not detailed in fetched pages.
**[UNCERTAIN]** for most of this section.

- The Gemini API does not expose region pinning on the free Developer API
  (`generativelanguage.googleapis.com`). Vertex AI offers `asia-south1` (Mumbai)
  endpoints with region-locked data residency — relevant if KSP requires data
  to stay in India.
- Typical latency from Bangalore to the global Gemini endpoint is observed at
  **~80–200 ms** per `embedContent` call (~empirical, varies). For the
  hackathon demo this is fine; for a production police deployment, route via
  Vertex AI `asia-south1` for both latency and compliance.
- For KSP production deployment, **data residency** (Karnataka Police data
  classification, IT Act 2000 + 2021 IT Rules) likely mandates Vertex AI Mumbai
  region. Confirm with KSP's IT/legal stakeholders before any pilot.

---

## 12. Comparison vs Catalyst QuickML RAG

We don't yet know QuickML's embedder details. The decision framework:

| Dimension | Gemini Embedding 001 | Catalyst QuickML RAG |
|---|---|---|
| Multilingual (Kannada) | Top MTEB Multilingual; empirically strong | Unknown — likely English-tuned **[UNCERTAIN]** |
| Cost | $0.15/M tokens (free tier for dev) | Bundled in Catalyst plan |
| Control | Full — pick dim, task_type, chunking | Likely black-box |
| Operational | We manage vector store + retrieval | Managed end-to-end |
| Lock-in | Portable (raw vectors) | Catalyst-only |

### A/B test criteria (pre-commit gate)

Build a **gold eval set** of ~150 KSP query→relevant-narrative pairs, split:
- 60% English queries
- 30% Kannada queries
- 10% code-switched

Score both pipelines on:
- **Recall@5** (primary)
- **MRR@10**
- **Kannada-only Recall@5** (separate cut — this is the deal-breaker)

**Decision rule**: ship Gemini if Kannada Recall@5 is ≥ 10 percentage points
above QuickML. Otherwise default to QuickML for simplicity and use Gemini only
as a re-ranker over QuickML's top-50.

---

## TL;DR for the team

- Model: **`gemini-embedding-001`**, **768 dims**, **L2-normalized**.
- Ingest with `task_type="RETRIEVAL_DOCUMENT"`, query with `"RETRIEVAL_QUERY"`.
- Chunk narratives to ~1500 tokens with 200-token overlap.
- Use Batch API for the 50K bulk ingest (50% off).
- Store `(case_id, chunk_idx, embedding, model_version, task_type)` in Catalyst
  NoSQL; do cosine in Python.
- Validate Kannada quality on a gold set **before** committing — official docs
  promise "100+ languages" but don't name Kannada.
