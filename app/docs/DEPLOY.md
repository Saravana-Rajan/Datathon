# Deploying KSP Saathi to Zoho Catalyst

This is the runbook for getting KSP Saathi running on production Catalyst infrastructure in the India data centre (`console.catalyst.zoho.in`). Total elapsed time on a clean Catalyst account: **~45 minutes**.

If you're new to Catalyst, skim [`../../docs/catalyst-reference.md`](../../docs/catalyst-reference.md) first — it lists every service we use and where to find it in the console.

---

## Prerequisites

Before you start, confirm all of the following:

### Accounts and credits

- [ ] **Zoho Catalyst account** on the India console (`console.catalyst.zoho.in`, not `.com`).
- [ ] **Catalyst free credits claimed** (required — every paid Catalyst service we use is covered by the hackathon credit grant).
- [ ] **Google Cloud project** with billing enabled, region `asia-south1`. Required APIs:
      `aiplatform.googleapis.com`, `generativelanguage.googleapis.com`, `maps-backend.googleapis.com`.
- [ ] **Neo4j AuraDB Free** instance provisioned in GCP `asia-south1`. Note the bolt URI, username, password.

### Tooling on your local machine

- [ ] **Node.js 20+** (`node --version`)
- [ ] **Python 3.11+** (`python --version`)
- [ ] **Catalyst CLI** installed and logged in:
      ```bash
      npm install -g zcatalyst-cli
      catalyst login
      ```
      The login flow opens a browser to `accounts.zoho.in` — make sure you pick the India DC.
- [ ] **gcloud CLI** authenticated against the project:
      ```bash
      gcloud auth login
      gcloud config set project ksp-saathi-prod
      ```

### Local repo state

- [ ] `app/.env` filled in with production values (copy from [`../.env.example`](../.env.example)).
- [ ] `app/backend/secrets/service-account.json` present (GCP service account with `aiplatform.user` + `generativelanguage.user` roles).
- [ ] All tests passing locally (`pytest` in `app/backend`, `npm run build` in `app/frontend`).

---

## Step 1 — Link the Local Repo to a Catalyst Project

From the repo root:

```bash
cd app/backend
catalyst init
```

When prompted:

- **Project type**: select an existing project (or create one called `ksp-saathi-prod`).
- **Region / DC**: India (`zoho.in`).
- **Features to enable**: Functions, Circuits, Authentication, Data Store, NoSQL, Stratus, Cache, API Gateway, Web Client Hosting (the frontend will share the same project).

This writes `backend/catalyst.json` and registers your local folder against the Catalyst project ID. Verify:

```bash
catalyst show
# Project ID: 10000000000000
# Region:     in
# Org ID:     60067540097
```

---

## Step 2 — Deploy the Backend (Functions + Circuits)

```bash
cd app/backend
catalyst deploy --only functions,circuits
```

What this does:

1. Packages each folder under `functions/` (hello, intent-router, sql-generator, cypher-generator, rag-retriever, synthesizer, audit-logger, pdf-exporter), uploads, and registers them as advanced-IO Functions on Python 3.11.
2. Parses `circuits/main-query-flow.yaml` and registers the orchestration flow.
3. Returns a public function URL for each handler.

Expected output (abridged):

```
✔ Deploying function hello                      → DONE
✔ Deploying function intent-router              → DONE
✔ Deploying function sql-generator              → DONE
✔ Deploying function cypher-generator           → DONE
✔ Deploying function rag-retriever              → DONE
✔ Deploying function synthesizer                → DONE
✔ Deploying function audit-logger               → DONE
✔ Deploying function pdf-exporter               → DONE
✔ Deploying circuit  main-query-flow            → DONE
Project deployed to: https://ksp-saathi-prod-XXXXXXXXX.development.catalystserverless.in
```

Smoke-test the health endpoint:

```bash
curl https://ksp-saathi-prod-XXXXXXXXX.development.catalystserverless.in/server/hello/
# {"status":"ok","region":"asia-south1","version":"<git sha>"}
```

If you hit `403 Forbidden`, jump to Step 4 (env vars) — most likely your auth token isn't in the Catalyst console yet.

---

## Step 3 — Deploy the Frontend (Web Client Hosting)

The Next.js app gets statically exported and served from Catalyst Web Client Hosting.

```bash
cd app/frontend
npm install
npm run build
catalyst deploy --only web-client-hosting
```

`npm run build` runs `next build` which produces a static export in `out/`. Catalyst Web Client Hosting then uploads `out/` and serves it from CDN-backed edge nodes inside the India DC.

Expected:

```
✔ Uploading 247 static assets         → DONE
✔ Activating client                    → DONE
Web client hosted at: https://ksp-saathi-prod-XXXXXXXXX.development.catalystserverless.in/app/
```

Visit that URL — you should see the KSP Saathi login screen.

---

## Step 4 — Set Environment Variables in the Catalyst Console

Catalyst Functions do **not** read from a local `.env` file when deployed. You must register variables in the console:

1. Open `console.catalyst.zoho.in` → your project → **Settings** → **Environment Variables**.
2. Add each key from [`../.env.example`](../.env.example) **except** the `NEXT_PUBLIC_*` keys (those are baked into the frontend build at `npm run build` time).
3. Toggle scope:
   - **Development** environment: your dev values
   - **Production** environment: production values

Required keys (server-side):

```
CATALYST_PROJECT_ID
CATALYST_ORG_ID
CATALYST_AUTH_TOKEN
CATALYST_API_BASE
CATALYST_REGION
GOOGLE_CLOUD_PROJECT_ID
GOOGLE_CLOUD_REGION
GEMINI_API_KEY
GEMINI_LIVE_MODEL
GEMINI_PRO_MODEL
GEMINI_EMBEDDING_MODEL
GOOGLE_MAPS_API_KEY
NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD
NEO4J_DATABASE
APP_ENV
APP_REGION
LOG_LEVEL
AUDIT_RETENTION_DAYS
SESSION_TIMEOUT_MINUTES
SESSION_MAX_TURNS
DEFAULT_LANGUAGE
ENABLE_KANNADA_VOICE
ENABLE_PREDICTIVE_HINTS
ENABLE_PDF_EXPORT
```

Service account JSON for GCP: upload via **Settings → Secret Files** (Catalyst mounts it at `/secrets/service-account.json` inside each function). Point `GOOGLE_APPLICATION_CREDENTIALS` at that path.

After saving env vars, redeploy functions so they pick up the new values:

```bash
cd app/backend
catalyst deploy --only functions
```

---

## Step 5 — Map a Custom Domain

In the Catalyst console:

1. **Domain Mappings** → **Add Domain**.
2. Enter your apex (e.g. `saathi.ksp-datathon.dev`).
3. Catalyst shows the DNS records you need to add at your registrar:
   - `CNAME saathi → ksp-saathi-prod.catalystserverless.in`
   - `TXT _zoho-verify → <verification-token>`
4. Wait for verification (usually < 5 minutes after DNS propagates).
5. Click **Provision SSL** — Catalyst issues a Let's Encrypt certificate automatically.

Once green, visit `https://saathi.ksp-datathon.dev/`. You should see the same login screen as Step 3.

For the API subdomain (`api.saathi.ksp-datathon.dev`), repeat the same flow and point it at the Functions endpoint. Then update `NEXT_PUBLIC_API_BASE_URL` and rebuild the frontend (Step 3) so the app calls the right URL.

---

## Step 6 — Promote to Production

Catalyst gives you two long-lived environments per project: `development` and `production`.

```bash
cd app/backend
catalyst push --env production
catalyst deploy --only functions,circuits --env production

cd ../frontend
npm run build
catalyst deploy --only web-client-hosting --env production
```

In the console, set the production environment variables (Step 4) under the **Production** scope, then enable the **min-instances: 1** setting on the synthesizer and intent-router functions — this prevents cold-start latency during demo day:

**Console → Functions → \<function\> → Configuration → Min Instances: 1**

---

## Post-Deploy Verification

Run all of these against the production URL and confirm expected output.

### Health check

```bash
curl https://api.saathi.ksp-datathon.dev/server/hello/
# {"status":"ok","region":"asia-south1","version":"<git sha>"}
```

### Auth — login flow

```bash
curl -X POST https://api.saathi.ksp-datathon.dev/baas/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"demo-inspector@ksp.local","password":"<seeded-pw>"}'
# Expect: { "access_token": "...", "role": "inspector", "expires_in": 3600 }
```

### Intent router — English

```bash
curl -X POST https://api.saathi.ksp-datathon.dev/server/intent-router/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"query": "show all chain snatchings near Indiranagar metro last 30 days"}'
# Expect: { "intent": "tabular_geo", "confidence": 0.94, "tools": ["sql_gen","h3_cluster"] }
```

### Intent router — Kannada

```bash
curl -X POST https://api.saathi.ksp-datathon.dev/server/intent-router/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"query": "ಈ ಸಂಶಯಿತನ ಮೇಲೆ ಮೊದಲು ಎಷ್ಟು ಪ್ರಕರಣಗಳಿವೆ?"}'
# Expect: { "intent": "graph_query", "confidence": >=0.85, "tools": ["cypher_gen"] }
```

### End-to-end Circuit

```bash
curl -X POST https://api.saathi.ksp-datathon.dev/server/circuit/main-query-flow/execute \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"query": "what are the top crime hotspots in Bengaluru this month?", "language": "en"}'
# Expect: streaming response with { "answer": "...", "viz_spec": {...}, "audit_id": "..." }
# Total latency target: < 3.5s
```

### Audit log

```bash
curl https://api.saathi.ksp-datathon.dev/server/audit-logger/?limit=5 \
     -H "Authorization: Bearer <token>"
# Expect: array of 5 most recent audit rows, each with user_id, role, raw_query, tool_calls, data_accessed
```

### Frontend reachable

```bash
curl -I https://saathi.ksp-datathon.dev/
# HTTP/2 200
# server: catalyst-web-client
# strict-transport-security: max-age=...
```

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `403 Forbidden` on every function | Auth token missing in console | Step 4 — add env vars and redeploy |
| `502 Bad Gateway` on first hit, works after | Cold start | Step 6 — set min-instances: 1 on hot path |
| Kannada voice silent | `GEMINI_API_KEY` empty in production env | Add it under **Production** scope, not just Development |
| Map panel blank | `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` baked from dev `.env` | Rebuild frontend with prod value, redeploy |
| Neo4j queries time out | AuraDB instance in wrong region | Recreate in `asia-south1` |
| PDF export missing fonts | Catalyst SmartBrowz font cache empty | First export takes ~10s as fonts warm; subsequent exports < 2s |

---

## Rollback

Catalyst keeps every deploy as a versioned artifact. To roll back:

```bash
catalyst deploy:rollback --env production --version <previous-version>
```

Find the version IDs in the console under **Deployments → History**.

---

## Demo-Day Checklist (T-24 hours)

- [ ] All env vars set in **Production** scope
- [ ] Min-instances=1 on `intent-router`, `synthesizer`, `audit-logger`
- [ ] Custom domain green, SSL valid > 30 days
- [ ] Audit log row created for at least one production query in the past hour
- [ ] Kannada voice round-trip tested end-to-end via mobile browser
- [ ] Backup demo video uploaded to a CDN URL outside Catalyst (in case Catalyst goes down — it won't, but)
- [ ] Hotspot device for venue WiFi failure prepared
- [ ] Pre-flight script (`scripts/preflight-demo.sh`) run to warm every function

Good luck.
