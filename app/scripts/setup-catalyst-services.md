# Sarvik — One-Time Catalyst Console Setup

This is the **manual** setup checklist for the Catalyst console pieces that **cannot** be expressed in `catalyst deploy`. Run through it once before the first `deploy-all.sh`. Expect ~30 minutes.

- **Console URL**  https://console.catalyst.zoho.in/baas/60074155874/project/47060000000020024/Development
- **Project ID**   `47060000000020024`
- **Org ID**       `60074155874`
- **Region / DC**  India (`zoho.in`)
- **Project name** `sarvik` (codename `ksp-saathi`)

Track progress with the checkbox on each step. If you re-run this on a new account, the same steps work — just substitute your own IDs.

---

## 0. Login + project confirmation

- [ ] Open https://console.catalyst.zoho.in and sign in with `saravanarajan.b@techjays.com`.
- [ ] Pick **Org `60074155874`** (top-left org switcher).
- [ ] Open project **sarvik** (PID `47060000000020024`).
- [ ] Confirm the URL bar shows `/project/47060000000020024/Development`. If it says `/Production`, switch to **Development** for initial setup.

[screenshot: org switcher + project list with sarvik selected]
[screenshot: dev/prod environment toggle (top-right)]

---

## 1. Data Store — relational tables

Path: **Develop → Data Store → + New Table**

Create the five tables below. For each: pick **Manual creation**, paste the columns exactly, mark primary keys, set the index where noted, then **Save**.

[screenshot: Data Store table list landing page]

### 1.1 `firs` (50K synthetic FIRs land here)

| Column | Type | Constraints |
|---|---|---|
| `fir_id` | VARCHAR(64) | **PK**, NOT NULL |
| `district` | VARCHAR(64) | NOT NULL, **Index** |
| `police_station` | VARCHAR(128) | NOT NULL, **Index** |
| `ipc_sections` | VARCHAR(255) | NOT NULL |
| `narrative_en` | TEXT | NULL |
| `narrative_kn` | TEXT | NULL |
| `incident_ts` | DATETIME | NOT NULL, **Index** |
| `reported_ts` | DATETIME | NOT NULL |
| `lat` | DECIMAL(10,7) | NULL |
| `lng` | DECIMAL(10,7) | NULL |
| `h3_index_r9` | VARCHAR(20) | NULL, **Index** *(H3 hex for hotspots)* |
| `status` | VARCHAR(32) | NOT NULL, default `OPEN` |
| `bias_review_status` | VARCHAR(32) | NOT NULL, default `none` |
| `created_at` | DATETIME | NOT NULL, auto |

- [ ] Created `firs`
- [ ] Composite index on `(district, incident_ts DESC)` — Console → table → **Indexes → + Add**
- [ ] Spatial index on `(lat, lng)` if available; otherwise rely on `h3_index_r9` index

[screenshot: firs schema after save, composite index visible]

### 1.2 `narrative_embeddings` (Gemini embedding vectors)

| Column | Type | Constraints |
|---|---|---|
| `embedding_id` | BIGINT | **PK**, auto-increment |
| `fir_id` | VARCHAR(64) | NOT NULL, **FK → firs.fir_id**, **Index** |
| `chunk_idx` | INT | NOT NULL |
| `language` | VARCHAR(8) | NOT NULL (`en` / `kn`) |
| `chunk_text` | TEXT | NOT NULL |
| `embedding` | TEXT | NOT NULL *(JSON-serialized 768-d float array — `gemini-embedding-001`)* |
| `model` | VARCHAR(64) | NOT NULL, default `gemini-embedding-001` |
| `created_at` | DATETIME | NOT NULL, auto |

- [ ] Created `narrative_embeddings`
- [ ] FK on `fir_id` enforced

### 1.3 `audit_log` (mandatory — feature #8 Explainable AI)

| Column | Type | Constraints |
|---|---|---|
| `audit_id` | VARCHAR(64) | **PK** |
| `user_id` | VARCHAR(64) | NOT NULL, **Index** |
| `role` | VARCHAR(32) | NOT NULL *(inspector / si / dsp / admin)* |
| `request_ts` | DATETIME | NOT NULL, **Index** |
| `language` | VARCHAR(8) | NOT NULL |
| `raw_query` | TEXT | NOT NULL |
| `intent` | VARCHAR(64) | NULL |
| `tool_calls` | TEXT | NOT NULL *(JSON array)* |
| `data_accessed` | TEXT | NOT NULL *(JSON: row IDs/case IDs)* |
| `answer_summary` | TEXT | NULL |
| `bias_flag` | BOOLEAN | NOT NULL, default `false` |
| `latency_ms` | INT | NOT NULL |
| `circuit_version` | VARCHAR(32) | NOT NULL |

- [ ] Created `audit_log`
- [ ] Retention configured (Console → table → **Settings → Retention**) to `AUDIT_RETENTION_DAYS` from env (default 365)

### 1.4 `session_state` (turn-by-turn conversation memory)

| Column | Type | Constraints |
|---|---|---|
| `session_id` | VARCHAR(64) | **PK** |
| `user_id` | VARCHAR(64) | NOT NULL, **Index** |
| `started_at` | DATETIME | NOT NULL |
| `last_turn_at` | DATETIME | NOT NULL, **Index** |
| `turn_count` | INT | NOT NULL, default 0 |
| `language` | VARCHAR(8) | NOT NULL |
| `state_json` | TEXT | NOT NULL *(serialized context window)* |
| `expires_at` | DATETIME | NOT NULL |

- [ ] Created `session_state`
- [ ] TTL: enable cron-driven sweep (see §6) OR Catalyst native TTL on `expires_at` if available

### 1.5 `bias_review_queue` (Section 18 — Bias-safe by design)

| Column | Type | Constraints |
|---|---|---|
| `queue_id` | BIGINT | **PK**, auto-increment |
| `audit_id` | VARCHAR(64) | NOT NULL, **FK → audit_log.audit_id** |
| `flagged_reason` | VARCHAR(128) | NOT NULL |
| `flagged_by` | VARCHAR(64) | NOT NULL *(`system` or user id)* |
| `severity` | VARCHAR(16) | NOT NULL *(low/med/high)* |
| `status` | VARCHAR(32) | NOT NULL, default `pending` |
| `reviewer_id` | VARCHAR(64) | NULL |
| `resolution` | TEXT | NULL |
| `created_at` | DATETIME | NOT NULL, auto |
| `resolved_at` | DATETIME | NULL |

- [ ] Created `bias_review_queue`

[screenshot: all 5 tables visible in Data Store list]

---

## 2. NoSQL — high-write tables

Path: **Develop → NoSQL → + Create Table**

NoSQL is for high-write / schemaless workloads. We use it for the things that don't need joins.

### 2.1 `chat_messages`

- **Partition key**: `session_id` (string)
- **Sort key**: `turn_idx` (number)
- Attributes (declared at write time):
  - `role` (string: user / assistant / tool)
  - `language` (string)
  - `text` (string)
  - `audio_url` (string, optional)
  - `tool_calls` (list, optional)
  - `ts` (number, epoch ms)
- TTL attribute: `expires_at` (epoch seconds, 30 days)

- [ ] Created `chat_messages`

### 2.2 `function_metrics` (per-function timings for observability)

- **Partition key**: `function_name` (string)
- **Sort key**: `ts_bucket_5m` (string, e.g. `2026-06-16T14:35`)
- Attributes: `p50_ms`, `p95_ms`, `p99_ms`, `count`, `errors`
- TTL: 14 days

- [ ] Created `function_metrics`

### 2.3 `voice_session_cache` (ephemeral Gemini Live tokens)

- **Partition key**: `session_id`
- Attributes: `live_session_token`, `model`, `language`, `started_at`
- TTL: 1 hour

- [ ] Created `voice_session_cache`

[screenshot: NoSQL table list with all three tables]

---

## 3. Authentication — Email + Google OAuth + custom roles

Path: **Develop → Authentication**

### 3.1 Enable providers

- [ ] **Settings → Sign-in Methods**: enable **Email/Password**
- [ ] Enable **Google OAuth**
  - Client ID: from GCP console → APIs & Services → Credentials
  - Client Secret: same source
  - Authorized redirect URI: `https://console.catalyst.zoho.in/baas/v1/project/47060000000020024/auth/callback/google`
- [ ] Disable all other providers (we explicitly only allow KSP officers)

[screenshot: Authentication → Sign-in Methods with Email + Google enabled, others greyed]

### 3.2 Custom claims / roles

Path: **Authentication → User Management → Custom Attributes**

Add these custom attributes (all string):

- [ ] `role`            — `inspector` | `si` | `dsp` | `admin`
- [ ] `district`        — Karnataka district code (e.g. `BNG-S`, `MYS`)
- [ ] `station_code`    — PS identifier
- [ ] `kn_voice_enabled` — `true` / `false`

These are injected into every JWT and read by `audit-logger` + `synthesizer` for RBAC (feature #9).

[screenshot: Custom Attributes panel showing the four fields]

### 3.3 Seed demo users (Development env only)

Create 4 demo users by hand:

- [ ] `demo-inspector@ksp.local` / role=`inspector` / district=`BNG-S`
- [ ] `demo-si@ksp.local` / role=`si` / district=`BNG-S`
- [ ] `demo-dsp@ksp.local` / role=`dsp` / district=`BNG-S`
- [ ] `demo-admin@ksp.local` / role=`admin`

Set strong throwaway passwords and store them in 1Password under "Sarvik Demo Users".

[screenshot: User Management with 4 demo users]

---

## 4. Stratus — object storage for PDF exports + audio

Path: **Develop → Stratus → + Create Bucket**

### 4.1 Bucket: `sarvik-pdfs`

- [ ] **Name**: `sarvik-pdfs`
- [ ] **Region**: India
- [ ] **Visibility**: Private (signed URLs only)
- [ ] **Lifecycle rule**: delete after `AUDIT_RETENTION_DAYS` (default 365)
- [ ] **CORS**: allow `GET, HEAD` from `https://saathi.ksp-datathon.dev` and `https://*.catalystserverless.in`

### 4.2 Bucket: `sarvik-audio` (voice turn recordings)

- [ ] **Name**: `sarvik-audio`
- [ ] **Region**: India
- [ ] **Visibility**: Private
- [ ] **Lifecycle**: delete after 30 days
- [ ] **CORS**: same as above

### 4.3 Bucket: `sarvik-uploads` (FIR PDF uploads from officers)

- [ ] **Name**: `sarvik-uploads`
- [ ] **Region**: India
- [ ] **Max file size**: 20 MB
- [ ] **Allowed MIME**: `application/pdf`

[screenshot: Stratus bucket list with 3 buckets]

---

## 5. QuickML — enable LLM serving + select Qwen 2.5 14B Instruct

Path: **AI → QuickML → LLM Serving**

- [ ] Click **Enable QuickML LLM Serving** for this project (one-click; provisions a serving endpoint on the India DC)
- [ ] **Model Catalog → Qwen 2.5 14B Instruct**: click **Deploy**
  - Inference profile: `low-latency` (single GPU, region India)
  - Concurrency: 4
  - Cold-start: keep warm (toggle ON for demo day; toggle OFF after the finale)
- [ ] **Model Catalog → Qwen 2.5 7B**: click **Deploy** (for intent-router; smaller/cheaper)
- [ ] After both show **Status = Running**, copy the **Endpoint URL** for each into env vars:
  - `QUICKML_QWEN_14B_URL`
  - `QUICKML_QWEN_7B_URL`
  - `QUICKML_API_KEY` (single key, project-scoped — visible in **QuickML → Settings**)

[screenshot: QuickML model catalog with both Qwen models in Running state]
[screenshot: QuickML endpoint detail showing URL + auth key]

### 5.1 QuickML RAG index

Path: **AI → QuickML → RAG Indexes → + New Index**

- [ ] **Name**: `sarvik-firs-rag`
- [ ] **Source**: Data Store table `firs` columns `narrative_en, narrative_kn`
- [ ] **Embedding model**: leave default (we override via `GEMINI_EMBEDDING_MODEL` at the function layer when QuickML quality is insufficient — see CLAUDE.md LLM strategy)
- [ ] **Chunk size**: 512 tokens, overlap 64
- [ ] **Run initial index** (takes ~20 min for 50K rows)

[screenshot: QuickML RAG index status = Ready]

---

## 6. Cron — scheduled jobs

Path: **Develop → Cron → + New Schedule**

- [ ] **Session cleanup** — sweeps `session_state` rows past `expires_at`
  - Function: `audit-logger` (sub-command via query param `?job=session_sweep`)
  - Schedule: every 15 min
- [ ] **Function metrics rollup** — aggregate NoSQL `function_metrics`
  - Function: `audit-logger?job=metrics_rollup`
  - Schedule: every 5 min
- [ ] **H3 hotspot reindex** — recompute hotspot tiles
  - Function: dedicated `h3-reindex` (deploy later) OR Pipeline
  - Schedule: nightly at 03:00 IST

[screenshot: Cron list with three schedules enabled]

---

## 7. API Gateway — routes

Path: **Develop → API Gateway → + New Route**

These map clean public paths onto Function URLs (the frontend talks to these).

| Route | Method | Target Function | Auth |
|---|---|---|---|
| `/api/v1/intent-router` | POST | `intent-router` | Required |
| `/api/v1/orchestrator` | POST | `orchestrator` | Required |
| `/api/v1/sql-generator` | POST | `sql-generator` | Required (role >= si) |
| `/api/v1/cypher-generator` | POST | `cypher-generator` | Required (role >= si) |
| `/api/v1/rag-retriever` | POST | `rag-retriever` | Required |
| `/api/v1/synthesizer` | POST | `synthesizer` | Required |
| `/api/v1/audit-log` | GET | `audit-logger` | Required (role >= dsp) |
| `/api/v1/pdf-export` | POST | `pdf-exporter` | Required |
| `/api/v1/health` | GET | `hello` | Public |

- [ ] All 9 routes created
- [ ] Each non-public route has **JWT verification** enabled (uses the Catalyst Authentication JWT issued in §3)
- [ ] CORS: allow `https://saathi.ksp-datathon.dev`, `https://*.catalystserverless.in`, `http://localhost:3000`
- [ ] Rate limit: 60 req/min per user on `/api/v1/orchestrator`

[screenshot: API Gateway route list with all 9 routes + JWT badges]

---

## 8. Environment Variables — secrets & API keys

Path: **Settings → Environment Variables**

Add each key in **both** Development and Production scopes. Mark sensitive ones as **Secret** (encrypted at rest).

### 8.1 Catalyst-internal

- [ ] `CATALYST_PROJECT_ID` = `47060000000020024`
- [ ] `CATALYST_ORG_ID` = `60074155874`
- [ ] `CATALYST_REGION` = `in`
- [ ] `CATALYST_API_BASE` = `https://console.catalyst.zoho.in/baas/v1/project/47060000000020024`

### 8.2 Google Cloud (Gemini + Maps)

- [ ] `GEMINI_API_KEY` *(secret)* — from GCP AI Studio
- [ ] `GEMINI_LIVE_MODEL` = `gemini-live-2.5-flash-preview`
- [ ] `GEMINI_PRO_MODEL` = `gemini-2.5-pro`
- [ ] `GEMINI_EMBEDDING_MODEL` = `gemini-embedding-001`
- [ ] `GOOGLE_MAPS_API_KEY` *(secret)*
- [ ] `GOOGLE_CLOUD_PROJECT_ID` = `ksp-saathi-prod`
- [ ] `GOOGLE_CLOUD_REGION` = `asia-south1`

### 8.3 Neo4j AuraDB

- [ ] `NEO4J_URI` *(secret)* — `neo4j+s://<id>.databases.neo4j.io`
- [ ] `NEO4J_USERNAME` = `neo4j`
- [ ] `NEO4J_PASSWORD` *(secret)*
- [ ] `NEO4J_DATABASE` = `neo4j`

### 8.4 QuickML endpoints (from §5)

- [ ] `QUICKML_QWEN_14B_URL`
- [ ] `QUICKML_QWEN_7B_URL`
- [ ] `QUICKML_API_KEY` *(secret)*
- [ ] `QUICKML_RAG_INDEX` = `sarvik-firs-rag`

### 8.5 App config

- [ ] `APP_ENV` = `development` (or `production` under Prod scope)
- [ ] `APP_REGION` = `asia-south1`
- [ ] `LOG_LEVEL` = `INFO`
- [ ] `AUDIT_RETENTION_DAYS` = `365`
- [ ] `SESSION_TIMEOUT_MINUTES` = `30`
- [ ] `SESSION_MAX_TURNS` = `40`
- [ ] `DEFAULT_LANGUAGE` = `en`
- [ ] `ENABLE_KANNADA_VOICE` = `true`
- [ ] `ENABLE_PREDICTIVE_HINTS` = `true`
- [ ] `ENABLE_PDF_EXPORT` = `true`

### 8.6 Stratus bucket names

- [ ] `STRATUS_BUCKET_PDFS` = `sarvik-pdfs`
- [ ] `STRATUS_BUCKET_AUDIO` = `sarvik-audio`
- [ ] `STRATUS_BUCKET_UPLOADS` = `sarvik-uploads`

### 8.7 GCP service account JSON

Path: **Settings → Secret Files**

- [ ] Upload `service-account.json` (GCP SA with `aiplatform.user` + `generativelanguage.user`)
- [ ] Mount path: `/secrets/service-account.json`
- [ ] Env var: `GOOGLE_APPLICATION_CREDENTIALS` = `/secrets/service-account.json`

[screenshot: Environment Variables page with all keys (values redacted)]
[screenshot: Secret Files showing service-account.json mounted]

---

## 9. Final sanity check

- [ ] `catalyst show` (locally) prints `Project ID: 47060000000020024` and `Region: in`
- [ ] Console → Functions → list shows all 9 function slots (after first `deploy-backend.sh` run)
- [ ] Console → Authentication → Users → 4 demo users exist
- [ ] Console → Data Store → 5 tables, all green
- [ ] Console → NoSQL → 3 tables, all green
- [ ] Console → Stratus → 3 buckets
- [ ] Console → QuickML → both Qwen models = Running, RAG index = Ready
- [ ] Console → API Gateway → 9 routes
- [ ] Console → Settings → Environment Variables → 30+ keys, all scoped Dev + Prod

Once all boxes are ticked, run:

```bash
bash app/scripts/deploy-all.sh --dry-run    # verify wiring
bash app/scripts/deploy-all.sh              # real deploy
bash app/scripts/verify-deploy.sh           # smoke test
```

If anything in §1–§8 changes after first deploy, you generally do **not** need to rerun the whole setup — only the affected step plus a `catalyst deploy --only functions` to pick up new env vars.
