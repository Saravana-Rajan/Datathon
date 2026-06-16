# Sarvik — Deploy Scripts

Real, runnable Bash for getting Sarvik (codename `ksp-saathi`) onto Zoho Catalyst (India DC, project `47060000000020024`).

Designed to be re-run safely: idempotent where possible, fails loudly when not, and writes a timestamped log per run under `app/.deploy-logs/`.

---

## File map

| File | Purpose | Typical invocation |
|---|---|---|
| `deploy-backend.sh` | Lints env, runs pytest per function, deploys each function via `catalyst deploy --only functions:<name>`, writes deployed URLs to `app/.env.deployed`. | `bash app/scripts/deploy-backend.sh` |
| `deploy-frontend.sh` | `npm install`, `npm run build`, `catalyst deploy --only web-client-hosting`. Appends frontend URL to `app/.env.deployed`. | `bash app/scripts/deploy-frontend.sh` |
| `deploy-all.sh` | Orchestrator. Runs backend, then frontend, then `verify-deploy.sh`. Aborts on any failure with a concrete next-step hint. | `bash app/scripts/deploy-all.sh` |
| `verify-deploy.sh` | Post-deploy smoke tests. Hits every function URL in `.env.deployed`, asserts HTTP 200 + expected JSON fields. Prints PASS/FAIL summary. | `bash app/scripts/verify-deploy.sh` |
| `setup-catalyst-services.md` | One-time manual checklist for the Catalyst console pieces that `catalyst deploy` can't do: Data Store tables, NoSQL tables, Authentication, Stratus buckets, QuickML model serving, API Gateway routes, env vars. | Open in your editor; tick boxes as you go. |
| `.env.deploy` *(optional, untracked)* | Source-controlled overrides for env vars consumed by the scripts (e.g. `EXPECTED_PROJECT_ID`, `CATALYST_CLI`, frontend `NEXT_PUBLIC_*`). | Auto-loaded by all scripts if present. |
| `../.env.deployed` *(generated)* | Output: `URL_<FUNCTION>=https://...` per deployed function plus `URL_FRONTEND=...`. Consumed by `verify-deploy.sh` and by the orchestrator at runtime. | Don't edit by hand. |

---

## First-time setup (~45 min, do this once)

1. Install prerequisites:
   ```bash
   # Node 20+, Python 3.11+, then:
   npm install -g zcatalyst-cli
   catalyst login            # pick India DC (accounts.zoho.in)
   ```
2. Work through every checkbox in `setup-catalyst-services.md`. This creates the Data Store tables, NoSQL tables, Stratus buckets, Auth providers, QuickML model endpoints, API Gateway routes, and environment variables in the Catalyst console.
3. (Optional) Create `app/scripts/.env.deploy` with any per-machine overrides. Example:
   ```bash
   EXPECTED_PROJECT_ID=47060000000020024
   EXPECTED_ORG_ID=60074155874
   EXPECTED_REGION=in
   CATALYST_CLI=catalyst
   NEXT_PUBLIC_API_BASE_URL=https://api.saathi.ksp-datathon.dev
   ```

---

## Day-to-day usage

### Deploy everything

```bash
bash app/scripts/deploy-all.sh
```

This is the one-command path. It runs backend (with tests), then frontend, then smoke-tests, and prints a clean URL list at the end.

### Iterate on a single function

```bash
bash app/scripts/deploy-backend.sh --only intent-router
```

Skips installation/test/deploy for every other function. Useful when you're hot-patching one handler.

### Skip tests (emergency only)

```bash
bash app/scripts/deploy-backend.sh --skip-tests
```

Tests gate deploys for a reason. Use this only when you're 100% sure and need to ship before the demo bell.

### Dry-run any script

Every script supports `--dry-run`. It prints exactly what would happen — no install, no deploy, no network writes. Use it before a high-stakes deploy:

```bash
bash app/scripts/deploy-all.sh --dry-run
```

### Just smoke-test what's already live

```bash
bash app/scripts/verify-deploy.sh
```

Reads `app/.env.deployed`, hits each function with a sanity payload, asserts 200 + key fields. Returns exit 1 if any probe fails. Set `VERIFY_AUTH_TOKEN=<jwt>` first if your routes require auth.

---

## CI / CD

`.github/workflows/deploy.yml` runs the same scripts on push to `main`. It needs three repo secrets:

| Secret | Source |
|---|---|
| `CATALYST_REFRESH_TOKEN` | OAuth refresh token from `catalyst login --dump-token` or the Catalyst self-service console |
| `CATALYST_CLIENT_ID` | Catalyst API console → Self-Client app |
| `CATALYST_CLIENT_SECRET` | Same |

Optional but recommended:

- `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` — baked into the frontend at build time
- `VERIFY_AUTH_TOKEN` — JWT used by smoke tests against auth-gated routes

The workflow runs four stages: **test → backend → frontend → smoke-test**, then posts a deploy summary back to the PR (or the commit, if pushed directly). Logs are uploaded as artifacts and retained for 14 days.

---

## How errors surface

All scripts:

- Use `set -Eeuo pipefail` so unhandled errors abort immediately.
- Trap `EXIT`, `INT`, `TERM`, `HUP` and print the tail of the run log on failure.
- Emit color-coded output (set `NO_COLOR=1` to disable).
- Write a per-run log to `app/.deploy-logs/<script>-<timestamp>.log`.

Common failure shapes and what to do:

| Symptom | Most likely cause | Fix |
|---|---|---|
| `catalyst CLI not found` | CLI not installed | `npm install -g zcatalyst-cli` |
| `catalyst account session active` step fails | Not logged in / token expired | `catalyst login` (India DC) |
| `Project ID mismatch` | `app/backend/catalyst.json` points at wrong project | `cd app/backend && catalyst init` and pick `sarvik` / `47060000000020024` |
| `pytest failed for <function>` | Real test failure | Fix the test (don't `--skip-tests` it) |
| `Could not parse deployed URL` | Catalyst CLI changed its output format | Script falls back to a deterministic URL guess; smoke test will still validate |
| `expected HTTP 200, got 403` in `verify-deploy.sh` | Env vars not set in Catalyst console | Open `setup-catalyst-services.md` §8 and confirm every key is set in the correct scope |

---

## Conventions

- **No emoji**, no Unicode noise — these scripts run in CI, on Git Bash, on macOS, and on Catalyst-hosted runners. Plain ASCII only.
- **Absolute project ID**: every script verifies `47060000000020024` before it deploys. If you fork to a new project, override with `EXPECTED_PROJECT_ID` in `.env.deploy`.
- **Single source of URLs**: `app/.env.deployed` is the only place deploy URLs live. The orchestrator function reads them from there at runtime; the smoke tester reads them in CI.
- **No bypassing tests in CI**: the workflow only honors `skip_tests=true` via manual `workflow_dispatch`; pushes to `main` always run pytest.

---

## When to run what

| Situation | Command |
|---|---|
| New machine / new account | Work through `setup-catalyst-services.md`, then `bash app/scripts/deploy-all.sh --dry-run`, then for real. |
| Pulled latest `main`, want to redeploy | `bash app/scripts/deploy-all.sh` |
| Touched one Python function | `bash app/scripts/deploy-backend.sh --only <name>` then `bash app/scripts/verify-deploy.sh` |
| Touched only the frontend | `bash app/scripts/deploy-frontend.sh` |
| Something in prod is on fire | `bash app/scripts/verify-deploy.sh` to localize the broken function, then targeted redeploy |
| Pre-finale T-24h checklist | `bash app/scripts/deploy-all.sh && bash app/scripts/verify-deploy.sh` against production scope; then the manual T-24h checklist in `docs/DEPLOY.md`. |
