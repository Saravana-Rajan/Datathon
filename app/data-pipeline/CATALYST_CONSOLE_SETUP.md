# Catalyst Console — Manual Setup Runbook (Sarvik / KSP Saathi)

> **Use this when** `create_catalyst_tables.py` returns FAIL (most likely cause:
> the Admin REST API on India DC declines the OAuth scope your self-client
> refresh token carries). The Console path always works.

Project: **Sarvik** • PID `47060000000020024` • Org `60074155874` • Region `IN`
Console root: <https://console.catalyst.zoho.in/baas/60074155874/project/47060000000020024/Development>

`catalyst.json` declares these features (all `enabled: true`) — provision them
in the order below:

```
datastore  ▸  nosql  ▸  stratus  ▸  cache  ▸  authentication
api-gateway ▸  zia  ▸  quickml  ▸  smartbrowz  ▸  pipelines  ▸  web-client-hosting
```

This runbook covers the 9 services Sarvik writes to / reads from at runtime.
Open each section, follow the clicks, paste in column names, save.

> Screenshot placeholders are referenced as `[shot: <id>]` — capture and drop
> them into `docs/screenshots/catalyst/` as you go.

---

## Section 1 — Data Store › `firs` table

**Console path**
`Cloud Scale ▸ Data Store ▸ + New Table` &nbsp;`[shot: ds-new-table]`

**Table settings**
- Table name: `firs`
- Description: *Karnataka FIR records (synthetic + real)*
- Created Time / Modified Time toggles: **ON**

**Columns** (add in order — Catalyst will create `ROWID`/`CREATEDTIME`/`MODIFIEDTIME` automatically):

| Column              | Type    | Length | Mandatory | Unique | Notes                                  |
| ------------------- | ------- | ------ | --------- | ------ | -------------------------------------- |
| `fir_no`            | VARCHAR | 32     | YES       | YES    | Primary key. `<STATION>/<YEAR>/<SEQ>`  |
| `station_name`      | VARCHAR | 128    | YES       |        |                                        |
| `station_lat`       | DECIMAL | —      |           |        |                                        |
| `station_lng`       | DECIMAL | —      |           |        |                                        |
| `district`          | VARCHAR | 64     | YES       |        |                                        |
| `date_registered`   | DATE    | —      | YES       |        |                                        |
| `time_registered`   | VARCHAR | 16     |           |        | `HH:MM:SS`                             |
| `crime_type`        | VARCHAR | 32     | YES       |        | enum, see `data/README.md`             |
| `ipc_sections`      | TEXT    | —      |           |        | JSON list `["379","411"]`              |
| `location_lat`      | DECIMAL | —      |           |        |                                        |
| `location_lng`      | DECIMAL | —      |           |        |                                        |
| `location_text`     | VARCHAR | 256    |           |        |                                        |
| `complainant`       | TEXT    | —      |           |        | JSON object                            |
| `accused`           | TEXT    | —      |           |        | JSON array                             |
| `status`            | VARCHAR | 32     |           |        |                                        |
| `narrative`         | TEXT    | —      |           |        | English (chunked for RAG)              |
| `narrative_kannada` | TEXT    | —      |           |        | Unicode Kannada (utf8mb4)              |

**Indexes** (`firs ▸ Indexes ▸ + New Index`) &nbsp;`[shot: ds-firs-indexes]`

| Index name                | Columns                                       | Unique |
| ------------------------- | --------------------------------------------- | ------ |
| `idx_firs_date`           | `date_registered`                             |        |
| `idx_firs_crime`          | `crime_type`                                  |        |
| `idx_firs_district`       | `district`                                    |        |
| `idx_firs_station`        | `station_name`                                |        |
| `idx_firs_geo_lat`        | `location_lat`                                |        |
| `idx_firs_geo_lng`        | `location_lng`                                |        |
| `idx_firs_dist_crime_dt`  | `district, crime_type, date_registered`       |        |

Confirm character set is **`utf8mb4`** (Catalyst default — needed for Kannada).

---

## Section 2 — Data Store › `narrative_embeddings` table

**Console path** `Cloud Scale ▸ Data Store ▸ + New Table` &nbsp;`[shot: ds-emb-new]`

| Column       | Type    | Length | Mandatory | Unique | Notes                              |
| ------------ | ------- | ------ | --------- | ------ | ---------------------------------- |
| `fir_no`     | VARCHAR | 32     | YES       | YES    | FK back to `firs.fir_no`           |
| `embedding`  | TEXT    | —      |           |        | JSON list of 768 floats (Gemini)   |
| `text`       | TEXT    | —      |           |        | The chunk that was embedded        |
| `crime_type` | VARCHAR | 32     |           |        | Denormalized for hot-path filters  |
| `district`   | VARCHAR | 64     |           |        | Denormalized for hot-path filters  |
| `date`       | DATE    | —      |           |        | Denormalized                       |

**Indexes**: `idx_emb_crime` on `crime_type`, `idx_emb_district` on `district`.

---

## Section 3 — NoSQL › `audit_logs`

**Console path** `Cloud Scale ▸ NoSQL ▸ + New Table` &nbsp;`[shot: nosql-audit]`

- Table name: `audit_logs`
- **Partition key**: `request_id` (STRING)
- **Sort key**: `step_index` (NUMBER)
- TTL: 90 days (optional)

Suggested item shape (no schema enforcement on NoSQL — these are the keys
`functions/audit-logger/` writes):

```json
{
  "request_id": "req_2026-06-17_abc123",
  "step_index": 0,
  "ts": "2026-06-17T11:04:33Z",
  "node": "intent-router",
  "input": "...",
  "output": "...",
  "latency_ms": 142,
  "model": "claude-opus-4-7"
}
```

---

## Section 4 — NoSQL › `sessions`

**Console path** `Cloud Scale ▸ NoSQL ▸ + New Table` &nbsp;`[shot: nosql-sessions]`

- Table name: `sessions`
- **Partition key**: `session_id` (STRING)
- **Sort key**: `turn_index` (NUMBER)

Stores conversational state for the multi-turn Saathi UI.

---

## Section 5 — NoSQL › `bias_review_queue`

**Console path** `Cloud Scale ▸ NoSQL ▸ + New Table` &nbsp;`[shot: nosql-bias]`

- Table name: `bias_review_queue`
- **Partition key**: `review_id` (STRING)
- **Sort key**: *(none — single-item lookups only)*

Holds answers flagged by the bias classifier for human review before display.

---

## Section 6 — Stratus › `case-pdfs` bucket

**Console path** `Cloud Scale ▸ Stratus ▸ + New Bucket` &nbsp;`[shot: stratus-bucket]`

- Bucket name: `case-pdfs`
- Access: **Private**
- Versioning: OFF
- Server-side encryption: **ON** (Catalyst-managed key is fine for hackathon)

Used by `functions/pdf-exporter/` for shareable case summaries.

---

## Section 7 — Cache

**Console path** `Cloud Scale ▸ Cache ▸ + New Segment` &nbsp;`[shot: cache-segment]`

- Segment name: `sarvik-default`
- Default TTL: `3600` seconds

Used by `functions/sql-generator/` and `functions/rag-retriever/` for memoizing
expensive ZCQL queries and embedding lookups.

---

## Section 8 — Authentication

**Console path** `Serverless ▸ Authentication ▸ Settings` &nbsp;`[shot: auth-settings]`

- Sign-in providers: **Google**, **Email/Password**
- Redirect URIs:
  - `https://sarvik-60074155874.development.catalystserverless.in/__catalyst/auth/callback`
  - `http://localhost:3000/auth/callback` (dev)
- Allowed origins: `http://localhost:3000`, the frontend domain

---

## Section 9 — API Gateway

**Console path** `Cloud Scale ▸ API Gateway ▸ + New Route` &nbsp;`[shot: gateway-route]`

Expose the `orchestrator` function as the only public entry point:

| Method | Path         | Target function    | Auth        |
| ------ | ------------ | ------------------ | ----------- |
| POST   | `/v1/ask`    | `orchestrator`     | App user    |
| GET    | `/v1/health` | `hello`            | None        |
| POST   | `/v1/pdf`    | `pdf-exporter`     | App user    |

Rate limit: 60 req/min per user. CORS: allow the frontend origin only.

---

## Verification

After completing all 9 sections, run:

```sh
cd app/data-pipeline
python verify_catalyst_setup.py
```

Expected output:

```
PASS  OAuth token minted from refresh_token
PASS  Data Store table 'firs' exists
PASS  Data Store table 'narrative_embeddings' exists
PASS  NoSQL table 'audit_logs' exists
PASS  NoSQL table 'sessions' exists
PASS  NoSQL table 'bias_review_queue' exists
PASS  Stratus bucket 'case-pdfs' exists
PASS  Round-trip on firs — insert + read + delete OK

READY for data load
```

If anything reads MISSING, jump back to the matching section above.

---

## Notes & gotchas

- **Why manual?** `zcatalyst-sdk` 1.3.0 (latest on PyPI) does not expose
  Data Store / NoSQL / Stratus DDL. The Admin REST API does, but only when
  your OAuth token carries the `ZohoCatalyst.projects.tables.CREATE` scope —
  which a self-client refresh token may not. The Console always works.
- **utf8mb4 / Kannada**: Catalyst's MySQL backend is utf8mb4 by default. The
  `narrative_kannada` column round-trips Unicode without extra configuration.
- **Circuits**: not available in the India DC for this project (`catalyst.json`
  note). Orchestration runs inside the `orchestrator` Python function instead —
  no Circuits setup needed.
- **Idempotency**: `create_catalyst_tables.py` treats HTTP 409 as SKIP, so it's
  safe to re-run while filling gaps from the Console.
