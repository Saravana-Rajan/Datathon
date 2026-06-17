# Sarvik — Neo4j Aura & Google Maps Setup

Project: **Karnataka Police AI (Sarvik)**
Deploy target: **Zoho Catalyst — India DC**
Owner: `saravanarajan@techjays.com`

> **DO NOT commit any secret value into this repo.** All real credentials live in the Catalyst Console environment variables (backend) and in `app/frontend/.env.local` (frontend, gitignored). The `PASTE_YOUR_…` placeholders in `app/backend/functions/orchestrator/catalyst-config.json` are templates only.

---

## Section A — Neo4j Aura DB connection

The DB connection credentials are **different** from the Aura API Client ID/Secret (see Section C). Don't confuse them.

### A1. Find the connection URI

1. Open the [Aura Console](https://console.neo4j.io/) > **Instances**.
2. Click your running instance.
3. Open the **Connect** tab.
4. Copy the `Connection URI` — it looks like:
   ```
   neo4j+s://12345abc.databases.neo4j.io
   ```
   This is the value for `NEO4J_URI`.

### A2. Username

The username is always:

```
neo4j
```

This is the value for `NEO4J_USERNAME`. (The `NEO4J_DATABASE` is also `neo4j` by default unless you created a named DB.)

### A3. Password

- The DB password was shown **only once** when the instance was created (Aura makes you download a `.txt` file with it).
- If you lost it: go to the instance page in the Aura Console and click **Reset password**. A new password is shown once — save it immediately.
- Store it locally **outside the repo**:

  ```bash
  # Linux / WSL / macOS
  mkdir -p ~/.config
  cat >> ~/.config/sarvik-secrets.env <<'EOF'
  NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
  NEO4J_USERNAME=neo4j
  NEO4J_PASSWORD=<paste-the-password>
  NEO4J_DATABASE=neo4j
  EOF
  chmod 600 ~/.config/sarvik-secrets.env
  ```

  On Windows PowerShell, the equivalent path is `$env:USERPROFILE\.config\sarvik-secrets.env`.

### A4. Quick connectivity test

With the values exported into your shell, run a one-liner against the Aura instance:

```bash
pip install neo4j
python - <<'PY'
import os
from neo4j import GraphDatabase

uri = os.environ["NEO4J_URI"]
user = os.environ["NEO4J_USERNAME"]
pwd = os.environ["NEO4J_PASSWORD"]
db = os.environ.get("NEO4J_DATABASE", "neo4j")

with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
    driver.verify_connectivity()
    with driver.session(database=db) as s:
        rec = s.run("RETURN 'ok' AS status, datetime() AS now").single()
        print(dict(rec))
PY
```

You should see `{'status': 'ok', 'now': <timestamp>}`. If you see an auth error, the password is wrong — reset it (A3).

### A5. Where to paste these in Catalyst

**Do not** edit the values inside `app/backend/functions/orchestrator/catalyst-config.json` and commit them. That file is a template. The real values go in the Catalyst Console:

1. Open the [Zoho Catalyst Console](https://console.catalyst.zoho.in/) (India DC).
2. Select the **Sarvik** project.
3. Go to **Serverless > Functions > orchestrator**.
4. Open the **Environment Variables** tab.
5. Add (or update):
   - `NEO4J_URI` → `neo4j+s://<your-instance>.databases.neo4j.io`
   - `NEO4J_USERNAME` → `neo4j`
   - `NEO4J_PASSWORD` → `<the password from A3>`
   - `NEO4J_DATABASE` → `neo4j`
6. **Save** and redeploy the orchestrator function so it picks up the new env vars.

---

## Section B — Google Maps API key

The frontend MapPanel currently renders `Google Maps key missing` because `NEXT_PUBLIC_GOOGLE_MAPS_KEY` is unset. Backend geocoding/Places calls also need a key as `MAPS_API_KEY`.

### B1. Create the key

1. Open [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** > **API key**.
3. In **APIs & Services > Library**, enable:
   - **Maps JavaScript API** (required — the frontend uses it)
   - **Places API** (optional — only if you use autocomplete/search)
   - **Geocoding API** (optional — backend address lookups)

### B2. Restrict the key (important — it ships in the static bundle)

Because Next.js static export embeds `NEXT_PUBLIC_*` vars into the public JS, the key will be readable by anyone visiting the site. Restrict it so a leak doesn't matter:

1. Click the key in the Credentials list.
2. **Application restrictions** → **HTTP referrers (web sites)**. Add:
   ```
   https://sarvik-60074155874.development.catalystserverless.in/*
   http://localhost:3000/*
   ```
3. **API restrictions** → **Restrict key** → select only the APIs enabled in B1.
4. Save.

### B3. Backend — Catalyst env var

Same flow as A5:

- Catalyst Console > Sarvik > **Functions > orchestrator > Environment Variables**
- Add `MAPS_API_KEY` → `<your Google Maps key>`
- Save and redeploy.

### B4. Frontend — `.env.local`

Create `app/frontend/.env.local` (this file is gitignored — confirm with `git status` before committing anything):

```bash
NEXT_PUBLIC_GOOGLE_MAPS_KEY=<your Google Maps key>
```

Then rebuild and redeploy the static export:

```bash
cd app/frontend
npm install
npm run build
# then push the build output to Catalyst as configured
```

After redeploy, MapPanel should render the live map instead of the empty state.

---

## Section C — Aura Client ID / Client Secret

The Client ID / Client Secret you pulled from the Aura console are credentials for the **Neo4j Aura Management API** — used to programmatically create, scale, pause, or delete Aura instances over REST. They are **not** used by the Sarvik app at runtime and **not** the same as the DB password.

For Sarvik you almost certainly do **not** need these. If you ever do:

- Store them in a password manager (1Password, Bitwarden, etc.), **or**
- Append them to `~/.config/sarvik-secrets.env` (chmod 600), e.g.:

  ```bash
  # ~/.config/sarvik-secrets.env
  AURA_API_CLIENT_ID=<id>
  AURA_API_CLIENT_SECRET=<secret>
  ```

- **Never** commit them. **Never** put them in `catalyst-config.json` or any frontend env file (they'd ship to the browser).

---

## Section D — Security warning: rotate the Client Secret

You pasted the Aura **Client Secret** into our chat. Assume it is now compromised (chat history may be retained, logged, or replayed). Rotate it before doing anything else:

1. Aura Console > **Account** (top-right) > **API Keys** (or **Account Settings > API Credentials**).
2. Find the Client ID you shared.
3. Click **Revoke** / **Delete** on the old key.
4. Click **Create** to generate a fresh Client ID + Secret pair.
5. Store the new pair per Section C — do not paste it back into chat.

Same rule going forward: never paste a live secret into a chat, a commit, an issue tracker, or a screenshot. If a secret touches an untrusted channel, treat it as burned and rotate immediately.

---

## Quick checklist

- [ ] DB password retrieved or reset, saved to `~/.config/sarvik-secrets.env`
- [ ] `python` connectivity test against Aura returns `ok`
- [ ] Catalyst Console env vars set: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `MAPS_API_KEY`
- [ ] Orchestrator function redeployed
- [ ] Google Maps key created and restricted to the Catalyst + localhost referrers
- [ ] `app/frontend/.env.local` contains `NEXT_PUBLIC_GOOGLE_MAPS_KEY`
- [ ] Frontend rebuilt and redeployed; MapPanel renders the live map
- [ ] Aura **Client Secret rotated** (the one shared in chat is burned)
- [ ] `git status` shows no secrets staged for commit
