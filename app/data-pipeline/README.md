# Data Pipeline — FIR JSONL → Catalyst Data Store

Quick guide for **Person A (Data Engineer)** to load 50K synthetic FIRs into
the KSP Saathi Catalyst Data Store.

---

## Prerequisites

1. **Python 3.10+** installed.
2. **FIR data file present** at `../../data/firs.jsonl` (50K records, ~91 MB).
   - Verify: `python -c "import os; print(os.path.getsize('../../data/firs.jsonl'))"`
   - Missing? Re-run `python data/generate_synthetic_firs.py` from the repo root.
3. **Catalyst project initialized** at `console.catalyst.zoho.in` (India DC).
   - User ID `60067540097` (Saravana Rajan).
4. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

5. **Environment variables** for `upload` mode (skip for `csv` mode):

   ```bash
   export CATALYST_PROJECT_ID=...                          # numeric id from console
   export CATALYST_PROJECT_KEY=...                         # project key
   export CATALYST_PROJECT_DOMAIN=https://api.catalyst.zoho.in
   export CATALYST_ENVIRONMENT=development                 # or "production"
   export CATALYST_USER_ID=60067540097
   export CATALYST_CLIENT_ID=...                           # self-client OAuth
   export CATALYST_CLIENT_SECRET=...
   export CATALYST_REFRESH_TOKEN=...
   ```

   On Windows PowerShell:

   ```powershell
   $env:CATALYST_PROJECT_ID = "..."
   $env:CATALYST_PROJECT_KEY = "..."
   # ...etc.
   ```

---

## The 3-step run

### Step 1 — Initialize the schema (one-time)

```bash
python schema_init.py --table firs
```

This prints **copy-paste-ready Catalyst Console instructions** for creating
the `firs` table with the right columns and indexes
(`date_registered`, `crime_type`, `station_name`, `district`,
`location_lat`, `location_lng`, plus a composite for time-series queries).

Optional: `python schema_init.py --create` attempts programmatic creation via
the SDK first (succeeds on plans where DDL is exposed; otherwise falls back to
the console steps automatically).

### Step 2 — Convert JSONL → CSV (sanity check / bulk import path)

```bash
python jsonl_to_catalyst.py \
  --input ../../data/firs.jsonl \
  --mode csv \
  --table firs
```

Produces `firs.csv` (~95 MB) with nested fields JSON-stringified. You can:
- Bulk-import via Catalyst Console (Data Store → Import → upload CSV), or
- Skip this and go straight to Step 3.

### Step 3 — Upload directly via the Catalyst SDK

```bash
python jsonl_to_catalyst.py \
  --input ../../data/firs.jsonl \
  --mode upload \
  --table firs \
  --batch-size 100
```

Behavior:
- Pulls all existing `fir_no` values up front (so re-runs skip duplicates).
- Inserts in batches of 100 (Catalyst's recommended page size).
- Live progress bar via tqdm.
- On per-row error: logs, skips, continues.
- Prints a final summary: read / written / skipped-existing / skipped-bad / errors.

Expected runtime: **~12–18 minutes** for 50K rows from a residential connection
(network-bound; batch-size 100, 500 batches × ~1.5–2 s each).

---

## Verify in Catalyst Console

Open Catalyst Console → Data Store → `firs` → Query Console:

```sql
-- Basic count
SELECT COUNT(*) FROM firs;
-- Expect: 50000

-- Date range sanity
SELECT MIN(date_registered), MAX(date_registered) FROM firs;
-- Expect: 2022-01-01 to 2025-12-31

-- Crime mix (top 5)
SELECT crime_type, COUNT(*) AS n
FROM firs
GROUP BY crime_type
ORDER BY n DESC
LIMIT 5;
-- Expect: vehicle_theft / cybercrime / fraud / burglary near the top

-- Bengaluru Urban check (~70% per generator design)
SELECT district, COUNT(*) AS n
FROM firs
WHERE district = 'Bengaluru Urban';
-- Expect: ~35,000

-- Kannada Unicode integrity
SELECT fir_no, narrative_kannada
FROM firs
LIMIT 3;
-- Expect: ಕನ್ನಡ script renders cleanly, not '???' or mojibake
```

If counts look wrong, see the **Re-run safety** section below.

---

## Re-run safety (idempotent)

You can re-run `--mode upload` as many times as you want:

- The script queries every existing `fir_no` in the table up front.
- Any row whose `fir_no` already exists is **skipped silently**.
- Network failure mid-run? Just re-run — only the missing rows are inserted.
- Partial upload? Same — the next run catches up.

To start completely fresh (destructive — be sure):

1. Catalyst Console → Data Store → `firs` → Settings → **Truncate Table**.
2. Re-run Step 3.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing required Catalyst env vars` | Set the env vars in the Prerequisites section. |
| `zcatalyst-sdk not installed` | `pip install -r requirements.txt` |
| Kannada shows as `???` | Table charset is not `utf8mb4`. Recreate the table (see schema_init.py output). |
| 100% rows in `skipped_existing` | Table already populated — that's the idempotency guard working. Truncate if you wanted a fresh load. |
| `Batch insert failed` log lines | Script auto-degrades to per-row insert to localize the bad record. Check the final summary for `fir_no`s that failed. |
| Slow upload | Lower `--batch-size 50` if you're seeing timeouts; raise to 200 if everything's fine. Default 100 is the sweet spot. |

---

## What this pipeline does NOT do (handled elsewhere)

- **Graph ingestion** — `neo4j_ingest.py` builds the criminal network from
  `accused` + `linked_fir_nos`.
- **H3 hotspot indexing** — `h3_hotspot_index.py` precomputes hex cells from
  `location_lat` / `location_lng`.

Those run **after** the Data Store load completes — they all read from `firs`.

---

# Embeddings ingestion (RAG layer) — `embed_narratives.py`

Embeds all 50,000 FIR narratives with Gemini and stores them for semantic
search by the `rag-retriever` Catalyst Function (Person B).

## Files in this section

| File | Purpose |
|---|---|
| `embed_narratives.py` | Main batch ingest. Embeds → writes to Catalyst NoSQL and/or local JSONL. |
| `vector_search.py` | Importable retrieval module. `LocalVectorStore` and `CatalystNosqlVectorStore` share the same `.search()` interface. |
| `embed_sample.py` | Smoke test — embeds 10 FIRs + 1 query, prints top-5 hits. Run FIRST. |

## Smoke test first (3 commands)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
python embed_sample.py --input ../../data/firs_sample.jsonl
```

A healthy smoke test prints 5 hits with cosine > 0.5 and a vehicle-theft FIR
at the top. If that looks sensible, proceed to full ingestion.

## Full 50K ingestion

### Dev mode — local JSONL (recommended first)

```bash
python embed_narratives.py \
    --input ../../data/firs.jsonl \
    --output-mode local-json \
    --local-out embeddings.jsonl \
    --batch 100 \
    --resume
```

Outputs `embeddings.jsonl` (~250 MB). Safe to Ctrl-C — re-running with
`--resume` skips already-embedded `fir_no`.

### Production mode — Catalyst NoSQL

```bash
export CATALYST_PROJECT_ID=...
export CATALYST_TOKEN=...

python embed_narratives.py \
    --input ../../data/firs.jsonl \
    --output-mode catalyst-nosql \
    --batch 100 \
    --resume
```

Writes to Catalyst NoSQL table `narrative_embeddings` (see schema below).

### Mirror to both (prod + local backup)

```bash
python embed_narratives.py --input ../../data/firs.jsonl \
    --output-mode both --batch 100 --resume
```

## When to use which mode

| Scenario | Mode |
|---|---|
| First-time setup, eyeballing retrieval quality, unit-testing | `local-json` |
| Demo day, Catalyst Function-served RAG queries | `catalyst-nosql` |
| Migrating after a model bump, want a local backup | `both` |
| Person B testing `rag-retriever` Function offline | `local-json` (load via `LocalVectorStore`) |

## Catalyst NoSQL schema for `narrative_embeddings`

| Column | Type |
|---|---|
| `fir_no` | TEXT (primary key) |
| `embedding` | JSON / TEXT (list of 768 floats) |
| `text` | TEXT |
| `crime_type` | TEXT |
| `district` | TEXT |
| `date` | DATE / TEXT |
| `lang` | TEXT |
| `task_type` | TEXT |
| `model` | TEXT |
| `dim` | NUMBER |

## Cost estimate

| Quantity | Value |
|---|---|
| Narratives | 50,000 |
| Avg tokens per chunk (EN + KN combined) | ~500 |
| Total tokens | ~25M |
| Gemini `embedding-001` standard price | $0.15 / 1M tokens |
| **Total cost (standard API)** | **~$3.75** |
| Total cost via Batch API (50% off) | ~$1.88 |

Cost is printed every 10 batches during the run.

## Resume after failure

`--resume` reads the destination once at start, builds a set of already-embedded
`fir_no`, and skips them. Safe to use on every invocation.

```bash
# Day 1
python embed_narratives.py --input ../../data/firs.jsonl \
    --output-mode catalyst-nosql --resume   # killed at 12K

# An hour later — picks up at 12K
python embed_narratives.py --input ../../data/firs.jsonl \
    --output-mode catalyst-nosql --resume
```

## How `rag-retriever` Function (Person B) uses this

`vector_search.py` is the only file Person B imports.

```python
from vector_search import CatalystNosqlVectorStore, embed_query

# Module-level — loads once per cold start (~25 s for 50K rows, ~150 MB)
STORE = CatalystNosqlVectorStore(table="narrative_embeddings")

def handler(event, context):
    user_query = event["query"]                  # "vehicle theft near MG Road"
    filters    = event.get("filters", {})        # {"district": "Bengaluru Urban"}

    q_vec = embed_query(user_query)              # task_type=RETRIEVAL_QUERY
    hits  = STORE.search(q_vec, top_k=5, filters=filters)

    return {"hits": [h.to_dict() for h in hits]}
```

Filters supported:
- exact: `{"crime_type": "vehicle_theft"}`
- IN list: `{"district": ["Bengaluru Urban", "Bengaluru Rural"]}`
- date range: `{"date": {"gte": "2024-01-01", "lte": "2024-12-31"}}`

For unit tests Person B swaps in one line:

```python
STORE = LocalVectorStore("embeddings.jsonl")  # same .search() interface
```

## Embedding contract (locked)

| Field | Value |
|---|---|
| Model | `gemini-embedding-001` |
| Dimension | 768 (Matryoshka, L2-normalised) |
| Task type at ingest | `RETRIEVAL_DOCUMENT` |
| Task type at query | `RETRIEVAL_QUERY` |
| Distance | Cosine (= dot product on L2-normed vectors) |
| Chunk strategy | One bilingual chunk per FIR: `header + EN + KN`, capped at 6000 chars |
| Language tag | `"bilingual"` on every row |

**Index drift safety**: `model` and `dim` are stored on every row. Upgrading to
`gemini-embedding-2` requires re-embedding the whole corpus — the spaces are
incompatible.

## Embeddings troubleshooting

| Symptom | Fix |
|---|---|
| `ImportError: google-genai` | `pip install -r requirements.txt` |
| `GEMINI_API_KEY env var not set` | `export GEMINI_API_KEY=...` (or set in Catalyst Env Vars) |
| `Catalyst credentials missing` | Set `CATALYST_PROJECT_ID` + `CATALYST_TOKEN`, OR run inside a Catalyst Function (the SDK auto-detects context). |
| `429 / 503` from Gemini | Built-in exponential backoff. If sustained, drop `--batch` to 50. |
| `KeyboardInterrupt` mid-run | Re-run with `--resume`. |
| Top hit score < 0.4 in smoke test | Query is genuinely far from the corpus — try another query. If all scores look like noise, check `dim` and `model` columns are consistent. |

---

*Last updated: 2026-06-16.  Owner: Person A.*

---

# Neo4j criminal network ingestion — `neo4j_ingest.py` (Person C)

Builds the graph that powers **Feature 5.5 — Criminal network visualization** (see `../../design.md`).

Owner: **Person C** (Graph + Predictive).

## What this builds

```
(Person {id, name, age, gender, centrality, case_count})
(FIR {fir_no, crime_type, date_registered, status, ipc_sections, ...})
(Station {name, lat, lng, district})
(Location {h3_index, h3_resolution, lat, lng, text})

(Person)-[:ACCUSED_IN]->(FIR)
(Person)-[:COMPLAINANT_IN]->(FIR)
(Person)-[:VICTIM_IN]->(FIR)
(FIR)-[:AT_STATION]->(Station)
(FIR)-[:OCCURRED_AT]->(Location)

# Derived (computed post-ingest by derived_edges.py):
(Person)-[:CO_ACCUSED_WITH {weight, sample_firs}]-(Person)
(Person)-[:CO_LOCATED_WITH {count, sample_h3}]-(Person)
```

## Prerequisites

1. **Neo4j AuraDB Free** account at https://console.neo4j.io. Create an instance in
   **asia-south1 (Mumbai)** — keeps India data residency consistent with Catalyst.
   Save the password (shown ONCE at creation).
2. **Python 3.10+** and `pip install -r requirements.txt` (adds `neo4j>=5.18.0`
   and `h3>=4.0.0`).
3. **Environment variables**:
   ```bash
   # bash / Git Bash
   export NEO4J_URI="neo4j+s://<your-id>.databases.neo4j.io"
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="<your-aura-password>"
   ```
   ```powershell
   # PowerShell
   $env:NEO4J_URI = "neo4j+s://<your-id>.databases.neo4j.io"
   $env:NEO4J_USER = "neo4j"
   $env:NEO4J_PASSWORD = "<your-aura-password>"
   ```
4. FIRs JSONL at `../../data/firs.jsonl` (Person A's output).

## The 3-step run

### Step 1 — Smoke test (100 rows, ~5s)
```bash
cd app/data-pipeline
python neo4j_ingest.py --input ../../data/firs_sample.jsonl --limit 100
```
Validates connectivity, applies schema, ingests, derives edges, prints top-10 gang-hub candidates.

### Step 2 — Mid-size validation (5K rows, ~30s)
```bash
python neo4j_ingest.py --input ../../data/firs.jsonl --limit 5000 --reset
```
`--reset` wipes the DB first so the smoke-test data doesn't pollute counts.

### Step 3 — Full ingest (50K rows, ~5min)
```bash
python neo4j_ingest.py --input ../../data/firs.jsonl --reset
```

## Verification queries (paste into Neo4j Browser)

Open Neo4j console → your instance → **Open with Neo4j Browser** → paste:

```cypher
-- Schema constraints exist (expect 4 rows)
SHOW CONSTRAINTS;

-- Node counts by label
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS n ORDER BY n DESC;

-- Top gang hub's 2-hop network (switch to graph view)
MATCH (p:Person)
WITH p ORDER BY p.centrality DESC LIMIT 1
MATCH path = (p)-[:CO_ACCUSED_WITH|CO_LOCATED_WITH*1..2]-(other)
RETURN path LIMIT 100;

-- Repeat offenders
MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR)
WITH p, count(f) AS cases WHERE cases >= 5
RETURN p.name, p.age, cases ORDER BY cases DESC LIMIT 20;

-- DySP killer query: suspects active across multiple stations
MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR)-[:AT_STATION]->(s:Station)
WITH p, count(DISTINCT s) AS stations, collect(DISTINCT s.name)[..5] AS sample
WHERE stations >= 3
RETURN p.name, stations, sample ORDER BY stations DESC LIMIT 10;
```

## Expected timings (AuraDB Free, asia-south1)

| Rows    | Primary | Derived + centrality | Total       |
|---------|--------:|---------------------:|------------:|
|     100 |    ~3 s |                 ~2 s |       ~5 s  |
|   5,000 |   ~25 s |                 ~5 s |      ~30 s  |
|  50,000 |  ~4 min |                ~1 min|      ~5 min |

## Known limitations (be honest in pitch)

1. **Person identity is a soft key** (`lower(name) + "::" + age`). Real CCTNS lacks
   a unique cross-station accused ID — this is the exact DySP pain point from
   `design.md` Section 3. The resolver will under-merge and over-merge; swap the
   `person_id()` function in `neo4j_ingest.py` when KSP supplies real IDs.
2. **No GDS/APOC on AuraDB Free.** Centrality uses a portable Cypher proxy
   (`case_count × log10(1 + co_accused_weight)`), not true PageRank.
3. **H3 resolution fixed at 8** (~0.7 km² hexes). Tune `H3_RESOLUTION` if needed.
4. **CO_LOCATED_WITH can explode on hot cells.** Fine for 50K, needs degree cap above 500K.

## CLI reference

```
python neo4j_ingest.py --input PATH [options]
  --input PATH          (required) JSONL of FIR records
  --limit N             Max rows to ingest (default: all)
  --batch N             Batch size for UNWIND (default: 500)
  --reset               Wipe DB before ingest (DESTRUCTIVE)
  --skip-derived        Don't compute CO_ACCUSED_WITH / CO_LOCATED_WITH
  --skip-centrality     Don't compute centrality scores

# Standalone re-run of derived stage (no re-ingest)
python derived_edges.py [--only co_accused|co_located|centrality] [--top-n 100]
```

## Backend consumption (`cypher_queries.py`)

The orchestrator's `cypher-generator` Function imports parameterized queries directly:

```python
from cypher_queries import find_criminal_network, find_similar_mo, \
    gang_hubs_by_district, repeat_offenders

cypher, params = find_criminal_network("Manpreet Chowdary", hops=2)
with driver.session() as s:
    records = list(s.run(cypher, **params))
```

Available queries:
- `find_criminal_network(person_name, hops, limit)` — 1-3 hop traversal around a named person
- `find_similar_mo(crime_type, days_back, district, limit)` — recent FIRs by crime type/area
- `gang_hubs_by_district(district, limit, min_cases)` — top centrality persons in an area
- `repeat_offenders(min_cases, crime_type, limit)` — Persons with N+ ACCUSED_IN edges
- `fir_full_context(fir_no)` — one FIR + its 1-hop neighbourhood
- `person_full_history(person_name, limit)` — every FIR a named person is accused in

All queries are parameterized (injection-safe) and bounded by `LIMIT` (no runaway scans).

## Troubleshooting (Neo4j)

| Symptom | Fix |
|---|---|
| `AuthError: unauthorized` | Wrong password — AuraDB shows it ONCE; reset from console. |
| `ServiceUnavailable: Failed to establish connection` | AuraDB Free auto-pauses after 3 days idle. Resume from console. |
| Ingest hangs on first batch | Another query is running (free tier is single-tenant). Close Neo4j Browser tabs. |
| Centrality score all 0 | You ran with `--skip-derived` or `--skip-centrality`. Re-run `python derived_edges.py`. |

---

*Neo4j section last updated: 2026-06-16.  Owner: Person C.*
