# Sarvik — Demo Runbook

> **Project:** Sarvik (codename `ksp-saathi`) — Datathon 2026 Challenge 01
> **Demo script reference:** [`docs/demo-script.md`](../../docs/demo-script.md)
> **Owner during demo week:** Person E (voice + demo). Person B sits at the laptop.

This folder contains the **only** scripts that should be run in the 24 hours
before a live Sarvik demo. Run them in the order below. Skip none.

```
app/demo/
├── README.md                ← you are here
├── requirements.txt         ← Python deps for this folder
├── golden_queries.json      ← the 5 demo queries (EN + KN) as data
├── seed_demo_data.py        ← seeds Catalyst Data Store + Auth + Cache
├── smoke_e2e.py             ← hits the live orchestrator with each query
└── prewarm.py               ← keeps Functions hot during the 10 min before stage
```

---

## Setup (once, on any laptop that will drive a demo)

```bash
cd app/demo
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then copy `../.env.example` to `../.env` and fill in:

* `CATALYST_API_BASE` (e.g. `https://api.catalyst.zoho.in`)
* `CATALYST_PROJECT_ID`
* `CATALYST_AUTH_TOKEN` (service token with Data Store + Auth + Cache + Function exec scopes)
* `CATALYST_ORG_ID`
* `CATALYST_ENVIRONMENT` = `development` or `production`

---

## T-24h (one day before demo) — seed the environment

```bash
python seed_demo_data.py --reset
```

What this does:

1. **Wipes** any previous demo rows tagged `sarvik_demo_v1` from the FIRs,
   Persons, and PersonLinks tables.
2. **Filters** `data/firs.jsonl` (50K records) → **1,000** records
   focused on MG Road / Indiranagar / Whitefield / Halasuru / Ulsoor.
   Inserts them into the Catalyst Data Store `FIRs` table.
3. **Creates** 3 demo officer accounts in Catalyst Auth with role
   custom claims:
   - `inspector.suresh@sarvik-demo.in` — Inspector role, MG Road station
   - `sho.lakshmi@sarvik-demo.in` — SHO role, Indiranagar station
   - `dcp.mehta@sarvik-demo.in` — DCP role, Bengaluru East
4. **Seeds** the Ravi Kumar criminal-network mini-dataset:
   - 5 persons (Ravi Kumar + 4 connections)
   - 6 relationship edges (`CO_ACCUSED_IN`, `LIVES_NEAR`, `CALLS`, `KNOWS`)
   - 4 linked FIRs across MG Road / Indiranagar / Whitefield
5. **Pre-caches** the 5 golden Q&A pairs in Catalyst Cache segment
   `sarvik_demo_golden` with a 7-day TTL. This is the `Ctrl+Shift+D`
   fallback referenced in `demo-script.md` Section C.2.

Idempotent flags:

* `--reset` — wipe first (use this once a day during demo week)
* `--dry-run` — print planned ops without calling Catalyst
* `--skip-firs` — keep existing FIRs, re-seed only officers/cache
* `--skip-cache` — keep existing cache entries (useful for partial reseeds)

> **Always re-run with `--reset` at T-24h.** Stale cached answers are the #2
> failure mode after WiFi (#1 per the demo-script risk table).

---

## T-1h (one hour before demo) — smoke test

```bash
python smoke_e2e.py
```

Hits the deployed orchestrator function with **all 5 golden queries in both
English and Kannada (10 calls total)**. For each call it asserts:

* HTTP 200
* `intent` matches expected_intent
* `viz_spec.type` matches expected_viz
* Result count is in `expected_count_range`
* Answer fragment appears in the response text (lenient — sources count too)
* End-to-end latency < **5,000 ms** (hard fail above this)
* End-to-end latency < **3,500 ms** (warning between 3.5s and 5s)

Output:

* Live coloured table in terminal
* `./results/<timestamp>/summary.json` — pass/fail per query
* `./results/<timestamp>/<query_id>__<lang>.json` — raw responses
* `./results/<timestamp>/results.txt` — GitHub-style markdown table to
  paste into Slack / email

Exit codes:

* `0` — all queries pass
* `1` — at least one fail (DO NOT run the live demo)
* `2` — `--strict` mode and at least one query was slow (>=3.5s)

Useful options:

```bash
python smoke_e2e.py --lang en             # English only (fast iteration)
python smoke_e2e.py --query q2_ravi_kumar_network   # one query only
python smoke_e2e.py --strict              # treat slow as fail
```

**If anything fails at T-1h:** run `seed_demo_data.py --reset` again, then
re-smoke. If still failing, switch the laptop into Cached Deterministic Mode
(`Ctrl+Shift+D` in the PWA) — the cache was seeded in step 1.

---

## T-12min (twelve minutes before stage) — prewarm Functions

```bash
python prewarm.py
```

This runs **10 cycles, 60 seconds apart**, hitting every Catalyst Function
with a `{"warmup": true}` payload. Each Function should short-circuit and
return immediately. The point is to pin a hot container so the first real
demo call doesn't pay a cold-start tax.

Defaults warm: `orchestrator`, `intent-router`, `sql-generator`,
`cypher-generator`, `rag-retriever`, `synthesizer`, `audit-logger`,
`pdf-exporter`.

Recommended: **run in the background** in a separate terminal that you can
glance at:

```bash
python prewarm.py --cycles 15 &
```

Useful options:

* `--cycles N` — number of cycles (default 10)
* `--interval S` — seconds between cycles (default 60)
* `--only orchestrator,intent-router` — warm a subset
* `--quiet` — only print slow/failing calls

The summary at the end tells you which functions still went cold during the
warm window. If any did, confirm `min-instances=1` is set on those functions
in the Catalyst Console.

---

## Demo time — the 5 golden queries (in order)

Once the team is on stage and Person B is at the laptop, the queries run
in this order. Person E narrates per `demo-script.md` Section B.3.

| # | Query (English) | Persona | Expected viz |
|---|-----------------|---------|---------------|
| 1 | Show me vehicle thefts near MG Road last month | PSI | map (h3 hotspot) |
| 2 | Show the criminal network of suspect Ravi Kumar | DySP | network_graph |
| 3 | Why did you say that? | DySP | audit_drawer |
| 4 | Predict next week's chain-snatching hotspots in Bengaluru South | PI | forecast_heatmap |
| 5 | (Same as Q1, after role switch to SHO) | SHO | map (expanded set) |

Kannada equivalents are in `golden_queries.json`. The full per-query
narration script is in `docs/demo-script.md` Section B.

### Live failure recovery — drill this

Per `demo-script.md` Section C.1 fallback ladder:

1. **Any query stalls > 5s** → B silently hits `Ctrl+Shift+D` to flip into
   Cached Deterministic Mode (answers served from the cache seeded above).
2. **Venue WiFi drops** → D switches laptop to phone hotspot.
3. **Catalyst goes down** → switch to side-stage local-only build.

---

## When to re-run what

| Trigger | seed | smoke | prewarm |
|---------|------|-------|---------|
| Day before demo | yes (`--reset`) | yes | no |
| Hour before demo | no | yes | no |
| 12 min before stage | no | no | yes |
| Quick code change to orchestrator | no | yes (`--lang en` for speed) | no |
| Adding a new golden query | edit json + yes (`--reset`) | yes | no |
| Cache TTL expired (>7 days) | yes | yes | no |

---

## Failure mode cheat sheet

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `seed_demo_data.py` says "Missing env vars" | `.env` not in `app/` | copy `.env.example` to `app/.env` |
| `seed` aborts on user create | service token lacks Auth scope | regen token with `ZohoCatalyst.users.ALL` |
| `smoke_e2e.py` HTTP 404 | wrong `YAKSHA_ORCHESTRATOR_FN` | check function name in Catalyst console |
| `smoke` all queries fail intent check | orchestrator routing bug | check Catalyst Function logs |
| `smoke` Q2 fails count check | Neo4j graph not loaded | run `app/data-pipeline/neo4j_ingest.py` |
| `smoke` Q4 fails | Zia AutoML model not trained | check `app/data-pipeline/` AutoML script |
| `prewarm` keeps showing cold calls | min-instances not set | Catalyst Console → Function → Scale → Min instances = 1 |

---

## Don't touch these on demo day

* `data/firs.jsonl` — frozen
* `golden_queries.json` — frozen (changing one breaks the cache)
* `seed_demo_data.py` constants (`TARGET_RECORD_COUNT`, `DEMO_TAG`, ...)

Anything in this folder is locked from T-24h onwards. If you find a bug at
T-1h, the right call is "use cached mode and fix it post-demo," not "edit
the seed script and re-run."

---

*Last reviewed: 2026-06-16. Owner: Person E (demo) + Person B (orchestrator).*
