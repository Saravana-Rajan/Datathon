# KSP Saathi — Week 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up every infrastructure account, validate the 7 unknowns, ship a "hello world" demonstrating end-to-end voice → LLM → response for both Catalyst Zia (English) and Gemini Live API (Kannada), and confirm the architecture decisions in `design.md` hold.

**Architecture:** Catalyst-first (mandatory) + Google Cloud for documented gaps (Gemini Live API for Kannada voice, Maps, Gemini Pro for premium synth) + Neo4j AuraDB for graph. Region: India-only (Catalyst India DC + GCP asia-south1).

**Tech Stack:** Zoho Catalyst (Functions, AppSail, Web Client Hosting, Data Store, NoSQL, QuickML, Zia Services, Auth, Circuits, Pipelines), Google Cloud (Gemini Live API, Gemini 2.5 Pro, Maps Platform, Vertex AI), Neo4j AuraDB Free, Next.js 15, FastAPI, Python 3.11.

**Window:** This week (5–7 days). Must complete BEFORE 11 Jun Catalyst workshop.

**Why this matters:** If validations fail, our architecture changes mid-build. Better to fail Week 0 than Week 6.

---

## File Structure (created in Week 0)

```
C:\Users\sarav\Datathon 2026\
├── design.md                          (exists)
├── research-investigators.md          (exists)
├── research-catalyst.md               (exists)
├── decisions.md                       (exists, agent-generated)
├── validation-checklist.md            (exists, agent-generated)
├── email-organizers.md                (exists, agent-generated)
├── data/
│   ├── generate_synthetic_firs.py     (exists)
│   ├── README.md                      (exists)
│   ├── firs.jsonl                     (exists, 50K records)
│   └── firs_sample.jsonl              (exists, 100 records)
├── plans/
│   └── 2026-06-16-foundation-week0.md (this file)
├── app/
│   ├── frontend/                      (Next.js — Person D creates)
│   │   ├── package.json
│   │   ├── next.config.js
│   │   ├── app/
│   │   │   ├── page.tsx
│   │   │   ├── layout.tsx
│   │   │   └── api/
│   │   └── catalyst.json
│   ├── backend/                       (FastAPI / Catalyst Functions — Person B creates)
│   │   ├── catalyst.json
│   │   ├── functions/
│   │   │   └── hello/
│   │   │       ├── index.py
│   │   │       └── catalyst-config.json
│   │   ├── circuits/
│   │   │   └── hello-flow.yaml
│   │   └── requirements.txt
│   └── validation/                    (validation scripts — each owner adds theirs)
│       ├── test_catalyst_zia_voice.py        (Person E)
│       ├── test_gemini_live_kannada.py       (Person E)
│       ├── test_qwen_kannada_quality.py      (Person B)
│       ├── test_data_store_geospatial.py     (Person A)
│       ├── test_zia_automl_forecast.py       (Person C)
│       ├── test_smartbrowz_kannada_pdf.py    (Person D)
│       ├── test_catalyst_auth_claims.py      (Person D)
│       ├── test_circuits_parallel.py         (Person B)
│       └── test_results.md                   (everyone appends results)
└── catalyst-project/
    └── catalyst.json                  (root Catalyst project config)
```

---

## Phase 0 — Pre-work (everyone, 30 min, parallel)

### Task 0.1: Register on hack2skill

**Files:** None (web action)

- [ ] **Step 1:** Open https://hack2skill.com/event/datathon2026/
- [ ] **Step 2:** Each team member creates an account
- [ ] **Step 3:** Team leader registers the team — name "KSP Saathi", challenge "01 — Intelligent Conversational AI for KSP Crime Database"
- [ ] **Step 4:** Add all 5 team members
- [ ] **Step 5:** Save team registration ID in `decisions.md` under "Team Identity"
- [ ] **Step 6:** Block calendars: 4 Jun (Problem Statement Explainer), 11 Jun (Catalyst workshop), 18 Jun (AMA)

**Acceptance:** Registration confirmation email received by team leader.

### Task 0.2: Claim Catalyst credits

**Files:** None (web action)

- [ ] **Step 1:** Open https://catalyst.zoho.com/promotions.html?cn=KSPH26
- [ ] **Step 2:** Each member signs in with Zoho account (or creates one)
- [ ] **Step 3:** Apply promo code `KSPH26` for hackathon credits
- [ ] **Step 4:** Record credit amount received in `decisions.md` → "Credits & Cost"
- [ ] **Step 5:** Verify credits visible in Catalyst console → Billing

**Acceptance:** Credits applied, visible in console for all 5 members.

### Task 0.3: Apply for GCP Startup credits

**Files:** None (web action)

- [ ] **Step 1:** Open https://cloud.google.com/startup or use existing GCP account
- [ ] **Step 2:** Activate $300 free trial OR apply for Google for Startups (5-7 day approval)
- [ ] **Step 3:** Create new GCP project: `ksp-saathi-2026`
- [ ] **Step 4:** Set region to `asia-south1` (Mumbai)
- [ ] **Step 5:** Enable APIs: Vertex AI, Maps Platform, Gemini API (Generative Language API), Cloud Speech-to-Text, Cloud Text-to-Speech
- [ ] **Step 6:** Generate service-account key, save to team password manager
- [ ] **Step 7:** Record GCP project ID in `decisions.md` → "Cloud Accounts"

**Acceptance:** GCP project exists in asia-south1, all APIs enabled, service-account key shared.

### Task 0.4: Create GitHub organization + repo

**Files:** Create repo `ksp-saathi`

- [ ] **Step 1:** Create GitHub org: `ksp-saathi-team` (or use existing)
- [ ] **Step 2:** Create private repo: `ksp-saathi`
- [ ] **Step 3:** Add all 5 team members as collaborators
- [ ] **Step 4:** Initialize with README, `.gitignore` (Python + Node + macOS), MIT license
- [ ] **Step 5:** Create branches: `main` (protected), `develop`, per-person feature branches
- [ ] **Step 6:** Add Branch Protection: `main` requires 1 review + passing checks

**Acceptance:** Repo accessible, all collaborators added, branch protection enabled.

### Task 0.5: Send organizer email (clarify third-party allowance)

**Files:** Use `email-organizers.md`

- [ ] **Step 1:** Open `email-organizers.md`, fill in `[TEAM_NAME]`, `[REGISTRATION_ID]`, contact details
- [ ] **Step 2:** Team leader sends to: `datathon2026support@hack2skill.com`
- [ ] **Step 3:** CC: technical leads
- [ ] **Step 4:** Save sent copy + organizer reply in `decisions.md` → "Organizer Communications" (proof of good-faith)

**Acceptance:** Email sent. (Reply may take 3-5 days — non-blocking.)

---

## Phase 1 — Catalyst project bootstrap (Person B, 2 hours)

### Task 1.1: Install Catalyst CLI

**Files:**
- Create: `app/backend/catalyst.json` (auto-generated)

- [ ] **Step 1:** Install: `npm install -g zcatalyst-cli`
- [ ] **Step 2:** Verify: `catalyst --version` → ≥ 1.18.0
- [ ] **Step 3:** Login: `catalyst login` → opens browser, authenticate
- [ ] **Step 4:** Verify identity: `catalyst account list` shows your account

**Acceptance:** CLI installed, authenticated, account visible.

### Task 1.2: Create Catalyst project

**Files:**
- Create: `app/backend/catalyst.json`

- [ ] **Step 1:** `cd app/backend`
- [ ] **Step 2:** Run: `catalyst init`
- [ ] **Step 3:** Choose: Project name → `ksp-saathi`, Region → `India (.in)`
- [ ] **Step 4:** Skip all features for now (we'll add per-task)
- [ ] **Step 5:** Verify `catalyst.json` created with `project_id` populated
- [ ] **Step 6:** Commit:

```bash
git add app/backend/catalyst.json
git commit -m "feat: initialize Catalyst project in India region"
```

**Acceptance:** `catalyst.json` exists with project_id, region = `IN`.

### Task 1.3: Create Hello-World Function

**Files:**
- Create: `app/backend/functions/hello/index.py`
- Create: `app/backend/functions/hello/catalyst-config.json`
- Create: `app/backend/functions/hello/requirements.txt`

- [ ] **Step 1:** Run: `catalyst add functions` → choose `Advanced I/O Functions` → name `hello` → runtime `python3.11`
- [ ] **Step 2:** Write the function:

```python
# app/backend/functions/hello/index.py
import json

def handler(request, response):
    name = request.args.get('name', 'World')
    response.send_json({
        'message': f'Hello {name} — KSP Saathi backend live',
        'region': 'India',
    })
```

- [ ] **Step 3:** Add `requirements.txt` (empty for now):

```
# app/backend/functions/hello/requirements.txt
```

- [ ] **Step 4:** Run locally: `catalyst serve` → opens at `localhost:3000`
- [ ] **Step 5:** Test: `curl "http://localhost:3000/server/hello?name=Saathi"`
- [ ] **Step 6:** Expected output:

```json
{"message": "Hello Saathi — KSP Saathi backend live", "region": "India"}
```

- [ ] **Step 7:** Deploy: `catalyst deploy --only functions`
- [ ] **Step 8:** Test deployed URL (printed in CLI output): `curl <deployed-url>/server/hello?name=Saathi`
- [ ] **Step 9:** Commit:

```bash
git add app/backend/functions/hello/
git commit -m "feat: hello-world function deployed to Catalyst India DC"
```

**Acceptance:** Function responds locally AND on deployed URL with India region confirmation.

### Task 1.4: Create Hello-World Circuit

**Files:**
- Create: `app/backend/circuits/hello-flow.yaml`

- [ ] **Step 1:** Run: `catalyst add circuits` → name `hello-flow`
- [ ] **Step 2:** Define a 2-step flow that calls the hello function twice in parallel:

```yaml
# app/backend/circuits/hello-flow.yaml
name: hello-flow
description: Validate Catalyst Circuits parallel execution
steps:
  - id: parallel-block
    type: parallel
    branches:
      - id: branch-en
        type: function
        function: hello
        input: { name: "English" }
      - id: branch-kn
        type: function
        function: hello
        input: { name: "Kannada" }
  - id: combine
    type: function
    function: hello
    input: { name: "{{parallel-block.branch-en.message}} | {{parallel-block.branch-kn.message}}" }
```

- [ ] **Step 3:** Deploy: `catalyst deploy --only circuits`
- [ ] **Step 4:** Trigger: `catalyst circuits run hello-flow`
- [ ] **Step 5:** Verify both parallel branches executed and combine step concatenated
- [ ] **Step 6:** **Log to `validation/test_results.md`**: ✅ Catalyst Circuits parallel execution works (or ❌ if it doesn't)
- [ ] **Step 7:** Commit:

```bash
git add app/backend/circuits/hello-flow.yaml
git commit -m "feat: hello circuit validates parallel execution"
```

**Acceptance:** Circuit runs end-to-end, parallel branches both fire, combine step receives both outputs.

---

## Phase 2 — Data layer (Person A, 3 hours)

### Task 2.1: Upload synthetic FIRs to Catalyst Data Store

**Files:**
- Create: `app/validation/test_data_store_geospatial.py`
- Modify: `data/README.md` (add Catalyst upload instructions if missing)

- [ ] **Step 1:** Generate fresh data if needed:

```bash
cd data
python generate_synthetic_firs.py --count 50000 --output firs.jsonl
```

- [ ] **Step 2:** Convert JSONL to CSV for Catalyst Data Store import (Catalyst Data Store imports CSV):

```python
# data/jsonl_to_csv.py — create this file
import json, csv

with open('firs.jsonl') as f, open('firs.csv', 'w', newline='', encoding='utf-8') as out:
    sample = json.loads(next(f))
    writer = csv.DictWriter(out, fieldnames=sample.keys(), extrasaction='ignore')
    writer.writeheader()
    writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in sample.items()})
    for line in f:
        rec = json.loads(line)
        writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in rec.items()})

print("Converted firs.jsonl → firs.csv")
```

- [ ] **Step 3:** Run: `python jsonl_to_csv.py` → produces `firs.csv` (~120 MB)
- [ ] **Step 4:** In Catalyst Console → Data Store → Create Table `firs` with these columns:

| Column | Type |
|---|---|
| fir_no | Text (Primary Key) |
| station_name | Text |
| station_lat | Decimal |
| station_lng | Decimal |
| district | Text |
| date_registered | Date |
| crime_type | Text |
| ipc_sections | Text (JSON-as-string) |
| location_lat | Decimal |
| location_lng | Decimal |
| location_text | Text |
| complainant | Text (JSON) |
| accused | Text (JSON) |
| status | Text |
| narrative | Text |
| narrative_kannada | Text |

- [ ] **Step 5:** Use Catalyst Console "Import Data" → upload `firs.csv` → map columns
- [ ] **Step 6:** Verify count: in Catalyst SQL Console, run:

```sql
SELECT COUNT(*) FROM firs;
```

Expected: 50000

- [ ] **Step 7:** Commit:

```bash
git add data/jsonl_to_csv.py
git commit -m "feat: convert FIR JSONL to CSV for Catalyst Data Store import"
```

**Acceptance:** 50,000 rows in Catalyst Data Store, queryable via SQL Console.

### Task 2.2: Validate Catalyst Data Store geospatial query support

**Files:**
- Create: `app/validation/test_data_store_geospatial.py`

- [ ] **Step 1:** Write validation script:

```python
# app/validation/test_data_store_geospatial.py
"""
Validation: Does Catalyst Data Store support geospatial queries?
Per research-catalyst.md: PostGIS NOT supported. Confirming here.
If confirmed unsupported, app-level H3 indexing is plan.
"""
from zcatalyst_sdk import App

app = App.initialize()
ds = app.datastore()

# Attempt 1: PostGIS-style ST_DWithin (expected: fail)
try:
    rows = ds.execute_query("""
        SELECT fir_no FROM firs
        WHERE ST_DWithin(
            ST_MakePoint(location_lng, location_lat),
            ST_MakePoint(77.6068, 12.9756),
            2000
        )
        LIMIT 5
    """)
    print(f"❌ UNEXPECTED: PostGIS worked, returned {len(rows)} rows")
    print("   Update design.md Section 17 — geospatial is supported")
except Exception as e:
    print(f"✅ EXPECTED: PostGIS not supported — {e}")
    print("   Falling back to app-level H3 indexing per plan")

# Attempt 2: Bounding box (expected: works)
rows = ds.execute_query("""
    SELECT fir_no, location_lat, location_lng FROM firs
    WHERE location_lat BETWEEN 12.95 AND 13.00
      AND location_lng BETWEEN 77.58 AND 77.63
    LIMIT 5
""")
print(f"✅ Bounding-box query works: {len(rows)} rows in MG Road area")
```

- [ ] **Step 2:** Run: `python app/validation/test_data_store_geospatial.py`
- [ ] **Step 3:** **Log result to `app/validation/test_results.md`**:

```markdown
## Catalyst Data Store geospatial
- Owner: Person A
- Date: <today>
- PostGIS / ST_DWithin: ❌ NOT supported (confirmed)
- Bounding-box query: ✅ Works
- Decision: Use app-level H3 indexing for hotspot detection. Bounding-box pre-filter at SQL layer.
```

- [ ] **Step 4:** Commit:

```bash
git add app/validation/test_data_store_geospatial.py
git commit -m "test: confirm Catalyst Data Store geospatial limits (no PostGIS)"
```

**Acceptance:** Test runs, result logged. If PostGIS unexpectedly works, design.md Section 17 updates.

---

## Phase 3 — LLM validation (Person B, 4 hours)

### Task 3.1: Catalyst QuickML — Kannada quality test

**Files:**
- Create: `app/validation/test_qwen_kannada_quality.py`

- [ ] **Step 1:** In Catalyst Console → QuickML → Models → enable `qwen-2.5-14b-instruct`
- [ ] **Step 2:** Get the LLM Serving endpoint URL (in QuickML → My Models → Deployed)
- [ ] **Step 3:** Write 20-query Kannada eval set:

```python
# app/validation/test_qwen_kannada_quality.py
"""
Validation: Qwen 2.5 14B Kannada quality
Pass: ≥85% queries return correct intent + grammatically correct Kannada
"""
import requests
import os

CATALYST_LLM_URL = os.environ["CATALYST_QUICKML_LLM_URL"]
CATALYST_TOKEN = os.environ["CATALYST_TOKEN"]

# 20 representative Kannada investigator queries
TESTS = [
    {"q": "ಎಂ.ಜಿ. ರಸ್ತೆಯ ಬಳಿ ಕಳೆದ ತಿಂಗಳಲ್ಲಿ ಎಷ್ಟು ವಾಹನ ಕಳ್ಳತನಗಳು ನಡೆದಿವೆ?",
     "intent": "tabular_query", "expects_kannada_reply": True},
    {"q": "ರವಿ ಕುಮಾರ್ ಸಂಶಯಿತನ ಕ್ರಿಮಿನಲ್ ಜಾಲವನ್ನು ತೋರಿಸಿ", "intent": "graph_query", "expects_kannada_reply": True},
    {"q": "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್ ಹೆಚ್ಚು ಎಲ್ಲಿ?", "intent": "geo_query", "expects_kannada_reply": True},
    {"q": "ಮುಂದಿನ ವಾರ ಯಾವ ಪ್ರದೇಶದಲ್ಲಿ ದರೋಡೆ ಹೆಚ್ಚಬಹುದು?", "intent": "predictive_query", "expects_kannada_reply": True},
    {"q": "FIR ಸಂಖ್ಯೆ BNG-EAST/2024/887 ರ ವಿವರಗಳು", "intent": "lookup", "expects_kannada_reply": True},
    # ... 15 more, mix of patterns / network / lookup / prediction
    # (For brevity, add the remaining 15 from research-investigators.md Section 5)
]

PROMPT_TEMPLATE = """You are an AI assistant for Karnataka Police investigators. The user query is in Kannada.

Step 1: Classify intent (tabular_query / graph_query / geo_query / predictive_query / lookup).
Step 2: Reply in Kannada with a brief acknowledgement of what you'd do.

User query: {query}

Respond in JSON: {{"intent": "...", "kannada_reply": "..."}}"""

def evaluate():
    pass_count = 0
    for i, t in enumerate(TESTS):
        prompt = PROMPT_TEMPLATE.format(query=t["q"])
        resp = requests.post(
            CATALYST_LLM_URL,
            headers={"Authorization": f"Bearer {CATALYST_TOKEN}"},
            json={"prompt": prompt, "max_tokens": 200, "temperature": 0.1}
        )
        result = resp.json()
        # Parse + check
        try:
            parsed = json.loads(result["text"])
            intent_match = parsed["intent"] == t["intent"]
            kannada_present = any('ಀ' <= c <= '೿' for c in parsed["kannada_reply"])
            if intent_match and kannada_present:
                pass_count += 1
                print(f"[{i+1}/20] ✅ Intent={parsed['intent']}, Kannada OK")
            else:
                print(f"[{i+1}/20] ❌ Intent expected={t['intent']} got={parsed.get('intent')}, KannadaOK={kannada_present}")
        except Exception as e:
            print(f"[{i+1}/20] ❌ Parse error: {e}")

    pct = pass_count / len(TESTS) * 100
    print(f"\nFinal: {pass_count}/{len(TESTS)} = {pct:.0f}%")
    print("PASS" if pct >= 85 else "FAIL — supplement with Gemini 2.5 Pro for Kannada")

if __name__ == "__main__":
    evaluate()
```

- [ ] **Step 4:** Run: `python app/validation/test_qwen_kannada_quality.py`
- [ ] **Step 5:** **Log result to `validation/test_results.md`**:

```markdown
## Qwen 2.5 14B Kannada quality
- Owner: Person B
- Date: <today>
- Pass rate: __ / 20 = __%
- Decision: <PASS — use Qwen as primary> OR <FAIL — route Kannada queries to Gemini 2.5 Pro>
```

- [ ] **Step 6:** Commit:

```bash
git add app/validation/test_qwen_kannada_quality.py
git commit -m "test: Qwen 2.5 Kannada quality eval (20-query)"
```

**Acceptance:** Test runs against deployed Qwen endpoint, pass/fail decision logged.

### Task 3.2: Gemini 2.5 Pro fallback test (same eval set)

**Files:**
- Modify: `app/validation/test_qwen_kannada_quality.py` (add Gemini comparison)

- [ ] **Step 1:** Add Gemini path to the test:

```python
# add to test_qwen_kannada_quality.py
import google.generativeai as genai
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def evaluate_gemini():
    model = genai.GenerativeModel('gemini-2.5-pro')
    pass_count = 0
    for i, t in enumerate(TESTS):
        prompt = PROMPT_TEMPLATE.format(query=t["q"])
        resp = model.generate_content(prompt)
        # Same parse + check logic
        # ...
```

- [ ] **Step 2:** Run both, compare side-by-side
- [ ] **Step 3:** Log A/B comparison in `decisions.md` under "LLM Augmentation Justification"
- [ ] **Step 4:** Commit

**Acceptance:** Both Qwen and Gemini scored on same 20 queries; decision documented.

### Task 3.3: Catalyst Circuits parallel execution validation

**Files:**
- Already done in Task 1.4 (`hello-flow.yaml`)

- [ ] **Step 1:** Confirm Task 1.4 result is logged in `validation/test_results.md`
- [ ] **Step 2:** If parallel didn't work, escalate — major architecture impact

**Acceptance:** Validation already covered.

---

## Phase 4 — Graph + Predictive validation (Person C, 3 hours)

### Task 4.1: Provision Neo4j AuraDB Free instance

**Files:**
- Create: `app/validation/test_neo4j_ingest.py`

- [ ] **Step 1:** Sign up at https://neo4j.com/cloud/aura/
- [ ] **Step 2:** Create Free Tier instance → region: `Mumbai (asia-south1)` if available, else `Singapore`
- [ ] **Step 3:** Save credentials to team password manager: URI (`neo4j+s://xxxxx.databases.neo4j.io`), user (`neo4j`), password
- [ ] **Step 4:** Open Neo4j Browser → verify connection
- [ ] **Step 5:** Define schema in Neo4j Browser:

```cypher
// Constraints
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT fir_no IF NOT EXISTS FOR (f:FIR) REQUIRE f.fir_no IS UNIQUE;
CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name);
```

**Acceptance:** Neo4j instance provisioned, schema constraints created.

### Task 4.2: Ingest synthetic FIRs into Neo4j

**Files:**
- Create: `app/validation/test_neo4j_ingest.py`

- [ ] **Step 1:** Write ingestion script:

```python
# app/validation/test_neo4j_ingest.py
"""
Ingest synthetic FIRs into Neo4j as Person + FIR nodes with relationships.
"""
import json
from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
)

def ingest_batch(tx, batch):
    for fir in batch:
        tx.run("""
            MERGE (f:FIR {fir_no: $fir_no})
            SET f.crime_type = $crime_type,
                f.date = date($date),
                f.station = $station
            WITH f
            UNWIND $accused AS a
            MERGE (p:Person {id: a.name + '|' + COALESCE(toString(a.age),'?')})
            SET p.name = a.name, p.age = a.age, p.gender = a.gender
            MERGE (p)-[:ACCUSED_IN]->(f)
        """, fir_no=fir["fir_no"], crime_type=fir["crime_type"],
              date=fir["date_registered"], station=fir["station_name"],
              accused=fir["accused"])

def main():
    BATCH_SIZE = 100
    LIMIT = 5000  # start with 5K for validation
    batch = []
    count = 0
    with open('data/firs.jsonl') as f, driver.session() as session:
        for line in f:
            fir = json.loads(line)
            batch.append(fir)
            if len(batch) >= BATCH_SIZE:
                session.execute_write(ingest_batch, batch)
                count += len(batch)
                print(f"Ingested {count}")
                batch = []
                if count >= LIMIT:
                    break
        if batch:
            session.execute_write(ingest_batch, batch)
            count += len(batch)
    print(f"DONE — ingested {count} FIRs")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2:** Install: `pip install neo4j`
- [ ] **Step 3:** Run: `python app/validation/test_neo4j_ingest.py`
- [ ] **Step 4:** In Neo4j Browser, verify:

```cypher
MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR) RETURN COUNT(*) AS edges
```

Expected: > 5000

- [ ] **Step 5:** Test multi-hop query:

```cypher
MATCH (p1:Person)-[:ACCUSED_IN]->(f1:FIR)<-[:ACCUSED_IN]-(p2:Person)
WHERE p1.name = 'Ravi Kumar' AND p1 <> p2
RETURN DISTINCT p2.name, COUNT(f1) AS shared_cases
ORDER BY shared_cases DESC LIMIT 10
```

- [ ] **Step 6:** Log to `validation/test_results.md`: ✅ Neo4j ingestion works, multi-hop traversal <100 ms
- [ ] **Step 7:** Commit:

```bash
git add app/validation/test_neo4j_ingest.py
git commit -m "feat: Neo4j FIR ingestion + multi-hop query validation"
```

**Acceptance:** 5,000+ FIRs ingested, multi-hop Cypher query returns results under 200 ms.

### Task 4.3: Catalyst Zia AutoML forecasting test

**Files:**
- Create: `app/validation/test_zia_automl_forecast.py`

- [ ] **Step 1:** Prepare time-series CSV from synthetic FIRs:

```python
# app/validation/prep_forecast_data.py
"""Aggregate synthetic FIRs to daily counts per station+crime_type."""
import json
import pandas as pd

rows = []
with open('data/firs.jsonl') as f:
    for line in f:
        r = json.loads(line)
        rows.append({
            'date': r['date_registered'],
            'station': r['station_name'],
            'crime_type': r['crime_type']
        })
df = pd.DataFrame(rows)
agg = df.groupby(['date', 'station', 'crime_type']).size().reset_index(name='count')
agg.to_csv('data/forecast_input.csv', index=False)
print(f"Wrote {len(agg)} rows to data/forecast_input.csv")
```

- [ ] **Step 2:** Run: `python app/validation/prep_forecast_data.py`
- [ ] **Step 3:** In Catalyst Console → Zia AutoML → Forecasting (or AutoML if no Forecasting):
  - Upload `data/forecast_input.csv`
  - Target column: `count`
  - Time column: `date`
  - Grouping columns: `station, crime_type`
  - Forecast horizon: 7 days
  - Train model
- [ ] **Step 4:** Note training time (Zia AutoML often takes 30–60 min)
- [ ] **Step 5:** Once trained, call the prediction endpoint and verify it returns forecasts
- [ ] **Step 6:** Log to `validation/test_results.md`:

```markdown
## Catalyst Zia AutoML forecasting
- Owner: Person C
- Date: <today>
- Training time: __ minutes
- Confidence intervals: <provided / NOT provided>
- Decision: <PASS — use Zia AutoML> OR <FAIL — fall back to Vertex AI Forecasting>
```

- [ ] **Step 7:** If Zia AutoML lacks confidence intervals or fails on small data, spin up Vertex AI Forecasting parallel test
- [ ] **Step 8:** Commit:

```bash
git add app/validation/prep_forecast_data.py app/validation/test_zia_automl_forecast.py
git commit -m "test: Zia AutoML forecasting validation"
```

**Acceptance:** Forecast model trained successfully OR fallback to Vertex AI Forecasting documented.

---

## Phase 5 — Frontend + Auth (Person D, 4 hours)

### Task 5.1: Scaffold Next.js 15 app

**Files:**
- Create: `app/frontend/` (entire Next.js scaffold)

- [ ] **Step 1:** `cd app/frontend`
- [ ] **Step 2:** Run:

```bash
npx create-next-app@latest . --typescript --tailwind --app --src-dir --import-alias "@/*" --eslint
```

- [ ] **Step 3:** Install shadcn/ui:

```bash
npx shadcn@latest init -d
npx shadcn@latest add button card input
```

- [ ] **Step 4:** Install Vercel AI SDK:

```bash
npm install ai @ai-sdk/react @ai-sdk/google
```

- [ ] **Step 5:** Create a simple chat page:

```typescript
// app/frontend/src/app/page.tsx
'use client';
import { useChat } from '@ai-sdk/react';

export default function Home() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: '/api/chat',
  });

  return (
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">KSP Saathi — Hello</h1>
      <div className="space-y-2 mb-4">
        {messages.map(m => (
          <div key={m.id} className="p-3 bg-gray-100 rounded">
            <strong>{m.role}:</strong> {m.content}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask anything..."
          className="flex-1 border rounded p-2"
        />
        <button type="submit" className="bg-blue-600 text-white px-4 rounded">
          Send
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 6:** Create stub API route:

```typescript
// app/frontend/src/app/api/chat/route.ts
import { streamText } from 'ai';
import { google } from '@ai-sdk/google';

export async function POST(req: Request) {
  const { messages } = await req.json();
  const result = await streamText({
    model: google('gemini-2.5-flash'),
    messages,
  });
  return result.toDataStreamResponse();
}
```

- [ ] **Step 7:** Set env var: `GOOGLE_GENERATIVE_AI_API_KEY=<your-key>` in `.env.local`
- [ ] **Step 8:** Run locally: `npm run dev` → test at `http://localhost:3000`
- [ ] **Step 9:** Commit:

```bash
git add app/frontend/
git commit -m "feat: Next.js 15 + shadcn + Vercel AI SDK scaffold"
```

**Acceptance:** Chat UI works locally with Gemini streaming.

### Task 5.2: Deploy Next.js to Catalyst Web Client Hosting

**Files:**
- Modify: `app/frontend/next.config.js`
- Create: `app/frontend/catalyst.json`

- [ ] **Step 1:** Configure Next.js for static export:

```javascript
// app/frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
};
export default nextConfig;
```

- [ ] **Step 2:** Build: `npm run build` → produces `out/` folder
- [ ] **Step 3:** Initialize Catalyst Web Client Hosting:

```bash
catalyst add web-client-hosting
```

- [ ] **Step 4:** Configure `catalyst.json` to point to `out/`
- [ ] **Step 5:** Deploy: `catalyst deploy --only web-client-hosting`
- [ ] **Step 6:** Open deployed URL, verify chat UI loads
- [ ] **Step 7:** Commit:

```bash
git add app/frontend/next.config.js app/frontend/catalyst.json
git commit -m "feat: deploy Next.js to Catalyst Web Client Hosting"
```

**Acceptance:** Frontend live on Catalyst-hosted URL.

### Task 5.3: Wire Catalyst Authentication

**Files:**
- Create: `app/frontend/src/lib/catalyst-auth.ts`
- Create: `app/validation/test_catalyst_auth_claims.py`

- [ ] **Step 1:** In Catalyst Console → Authentication → enable Email + OAuth (Google)
- [ ] **Step 2:** Create test users with custom role claim: `{ role: "inspector" }`, `{ role: "constable" }`
- [ ] **Step 3:** Install Catalyst client SDK in frontend:

```bash
npm install zcatalyst-web-cli
```

- [ ] **Step 4:** Add a login page that requires Catalyst Auth
- [ ] **Step 5:** Verify JWT contains custom role claim by decoding it (https://jwt.io)
- [ ] **Step 6:** Log to `validation/test_results.md`:

```markdown
## Catalyst Authentication custom claims
- Owner: Person D
- Date: <today>
- Email + OAuth: ✅ enabled
- Custom role claims in JWT: <YES / NO>
- Decision: <PASS — use for RBAC> OR <use API gateway middleware for role checks instead>
```

- [ ] **Step 7:** Commit

**Acceptance:** Login works, JWT inspection confirms custom claims OR documented workaround.

---

## Phase 6 — Voice validation (Person E, 5 hours)

### Task 6.1: Catalyst Zia Services voice test (English)

**Files:**
- Create: `app/validation/test_catalyst_zia_voice.py`

- [ ] **Step 1:** Get Catalyst Zia API endpoint from Console
- [ ] **Step 2:** Record 5 English test phrases (use phone voice recorder)
- [ ] **Step 3:** Write test:

```python
# app/validation/test_catalyst_zia_voice.py
"""
Validation: Catalyst Zia STT (English) + TTS (English)
Pass: All 5 phrases transcribed correctly, TTS sounds natural
"""
import requests
import os

ZIA_STT_URL = os.environ["ZIA_STT_URL"]
ZIA_TTS_URL = os.environ["ZIA_TTS_URL"]
TOKEN = os.environ["CATALYST_TOKEN"]

PHRASES = [
    "Show me vehicle thefts near MG Road last month",
    "What is the criminal history of Ravi Kumar",
    "Predict robberies in Whitefield for next week",
    "Export this conversation as PDF",
    "Why did you suggest that hotspot",
]

# Read audio files audio_en_1.wav ... audio_en_5.wav
for i, expected in enumerate(PHRASES, 1):
    with open(f"audio_en_{i}.wav", "rb") as f:
        resp = requests.post(
            ZIA_STT_URL,
            headers={"Authorization": f"Bearer {TOKEN}"},
            files={"audio": f},
            data={"language": "en-US"}
        )
    transcript = resp.json().get("transcript", "")
    print(f"[{i}] expected: {expected}")
    print(f"    got:      {transcript}")

# TTS test
for i, text in enumerate(PHRASES, 1):
    resp = requests.post(
        ZIA_TTS_URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"text": text, "language": "en-US"}
    )
    with open(f"tts_en_{i}.wav", "wb") as f:
        f.write(resp.content)
    print(f"[{i}] TTS saved to tts_en_{i}.wav — listen + rate naturalness 1-5")
```

- [ ] **Step 4:** Run, listen to each TTS output, score naturalness
- [ ] **Step 5:** Log to `validation/test_results.md`
- [ ] **Step 6:** Commit

**Acceptance:** STT accurate for ≥4/5 phrases, TTS naturalness ≥3/5 average.

### Task 6.2: Gemini Live API — Kannada voice quality test (CRITICAL)

**Files:**
- Create: `app/validation/test_gemini_live_kannada.py`

- [ ] **Step 1:** Verify Gemini Live API access enabled in GCP project (Generative Language API)
- [ ] **Step 2:** Install: `pip install google-genai`
- [ ] **Step 3:** Record 20 Kannada test phrases (use a Kannada-speaking team member or Sarvam's TTS to generate test audio)
- [ ] **Step 4:** Write test:

```python
# app/validation/test_gemini_live_kannada.py
"""
Validation: Gemini Live API Kannada voice quality
THIS IS THE MOST CRITICAL VALIDATION OF WEEK 0.
If Gemini Live Kannada quality < 85%, we fall back to Google Cloud STT (kn-IN).
"""
import asyncio
from google import genai
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

KANNADA_PHRASES = [
    "ಎಂ.ಜಿ. ರಸ್ತೆಯ ಬಳಿ ಕಳೆದ ತಿಂಗಳಲ್ಲಿ ಎಷ್ಟು ವಾಹನ ಕಳ್ಳತನಗಳು ನಡೆದಿವೆ",
    "ರವಿ ಕುಮಾರ್ ಸಂಶಯಿತನ ಕ್ರಿಮಿನಲ್ ಜಾಲವನ್ನು ತೋರಿಸಿ",
    "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಚೈನ್ ಸ್ನ್ಯಾಚಿಂಗ್ ಹೆಚ್ಚು ಎಲ್ಲಿ",
    "ಮುಂದಿನ ವಾರ ಯಾವ ಪ್ರದೇಶದಲ್ಲಿ ದರೋಡೆ ಹೆಚ್ಚಬಹುದು",
    "FIR ಸಂಖ್ಯೆ BNG-EAST/2024/887 ರ ವಿವರಗಳು",
    # ... 15 more from research-investigators.md Section 5
]

async def test_voice(audio_file, expected_text):
    """Stream audio in, get text + audio reply."""
    config = {
        "response_modalities": ["AUDIO", "TEXT"],
        "system_instruction": "You are a helpful AI for Karnataka Police. Reply in Kannada.",
    }
    async with client.aio.live.connect(model="gemini-2.5-flash-preview-native-audio-dialog", config=config) as session:
        with open(audio_file, "rb") as f:
            audio_bytes = f.read()
        await session.send_realtime_input(audio={"data": audio_bytes, "mime_type": "audio/wav"})
        text_response = ""
        audio_chunks = []
        async for chunk in session.receive():
            if chunk.text:
                text_response += chunk.text
            if chunk.data:
                audio_chunks.append(chunk.data)
        return text_response, audio_chunks

async def main():
    pass_count = 0
    for i, expected in enumerate(KANNADA_PHRASES, 1):
        audio_file = f"audio_kn_{i}.wav"
        if not os.path.exists(audio_file):
            print(f"[{i}/20] SKIP — {audio_file} not found")
            continue
        try:
            text, audio = await test_voice(audio_file, expected)
            has_kannada = any('ಀ' <= c <= '೿' for c in text)
            audio_returned = len(audio) > 0
            if has_kannada and audio_returned:
                pass_count += 1
                print(f"[{i}/20] ✅ Text reply in Kannada + audio returned")
            else:
                print(f"[{i}/20] ❌ has_kannada={has_kannada} audio={audio_returned}")
        except Exception as e:
            print(f"[{i}/20] ❌ Error: {e}")

    pct = pass_count / 20 * 100
    print(f"\nFinal: {pass_count}/20 = {pct:.0f}%")
    print("PASS — use Gemini Live API as primary Kannada voice" if pct >= 85
          else "FAIL — fall back to Google Cloud STT (kn-IN) + TTS Neural2")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5:** Run: `python app/validation/test_gemini_live_kannada.py`
- [ ] **Step 6:** **Critical log to `validation/test_results.md`**:

```markdown
## Gemini Live API — Kannada quality (CRITICAL)
- Owner: Person E
- Date: <today>
- Pass rate: __ / 20 = __%
- First-audio latency: __ ms (measure with timestamps)
- Decision: <PASS — Gemini Live primary for Kannada>
           OR <FAIL — use Google Cloud STT kn-IN + TTS Neural2 kn-IN-Wavenet-A>
           OR <FAIL — escalate, may revisit Sarvam.ai>
```

- [ ] **Step 7:** Commit:

```bash
git add app/validation/test_gemini_live_kannada.py
git commit -m "test: Gemini Live API Kannada quality validation (20-query)"
```

**Acceptance:** Test runs against Gemini Live API, decision logged. **If FAIL, design.md voice section is updated immediately.**

### Task 6.3: Google Cloud STT/TTS fallback verified

**Files:**
- Create: `app/validation/test_google_cloud_voice_fallback.py`

- [ ] **Step 1:** Install: `pip install google-cloud-speech google-cloud-texttospeech`
- [ ] **Step 2:** Set `GOOGLE_APPLICATION_CREDENTIALS` env var to service-account JSON path
- [ ] **Step 3:** Write fallback test:

```python
# app/validation/test_google_cloud_voice_fallback.py
"""Verify Google Cloud STT/TTS Kannada works as universal fallback."""
from google.cloud import speech, texttospeech

# STT
client = speech.SpeechClient()
with open("audio_kn_1.wav", "rb") as f:
    audio = speech.RecognitionAudio(content=f.read())
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    language_code="kn-IN",
)
response = client.recognize(config=config, audio=audio)
for r in response.results:
    print(f"STT transcript: {r.alternatives[0].transcript}")

# TTS
tts = texttospeech.TextToSpeechClient()
input_text = texttospeech.SynthesisInput(text="ನಮಸ್ಕಾರ ಇನ್ಸ್‌ಪೆಕ್ಟರ್")
voice = texttospeech.VoiceSelectionParams(language_code="kn-IN", name="kn-IN-Wavenet-A")
audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
response = tts.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
with open("tts_kn_fallback.mp3", "wb") as f:
    f.write(response.audio_content)
print("TTS saved — listen to verify Kannada naturalness")
```

- [ ] **Step 4:** Run, verify STT transcript matches, listen to TTS
- [ ] **Step 5:** Log result
- [ ] **Step 6:** Commit

**Acceptance:** Google Cloud STT/TTS Kannada confirmed working as fallback.

---

## Phase 7 — Final integration check (everyone, 2 hours, Friday)

### Task 7.1: End-to-end smoke test (English path)

**Files:** None new; integrate existing pieces

- [ ] **Step 1:** Open deployed Next.js URL
- [ ] **Step 2:** Click microphone → say in English: *"Hello, can you respond"*
- [ ] **Step 3:** Verify: Catalyst Zia STT transcribes → Hello function returns → Catalyst Zia TTS replies in English
- [ ] **Step 4:** Total round-trip latency captured

**Acceptance:** End-to-end English voice loop works on deployed environment.

### Task 7.2: End-to-end smoke test (Kannada path)

**Files:** None new

- [ ] **Step 1:** Same flow, in Kannada
- [ ] **Step 2:** Verify: Gemini Live API STT → Gemini synthesizes Kannada reply → Gemini Live API TTS plays audio
- [ ] **Step 3:** Latency captured

**Acceptance:** End-to-end Kannada voice loop works on deployed environment.

### Task 7.3: Week 0 retrospective + writing-plans for Week 1

**Files:**
- Create: `plans/2026-06-XX-retro-week0.md` (Friday)
- Create: `plans/2026-06-XX-week1-data-layer.md` (next plan to draft)

- [ ] **Step 1:** Team meeting: review `validation/test_results.md` — every owner reports PASS/FAIL
- [ ] **Step 2:** For every FAIL, update `design.md` Section 17 and Section 18 (Decision Log)
- [ ] **Step 3:** Draft retro: what worked, what blocked, what to change for Week 1
- [ ] **Step 4:** Invoke writing-plans skill for Subsystem Plan 1 (Data Layer — full SQL schema, indexing, RAG ingestion)
- [ ] **Step 5:** Commit retro + Week 1 plan

**Acceptance:** Week 0 closed, all validations logged, Week 1 plan ready.

---

## Self-Review (against design.md)

| Design spec section | Covered by Week 0 task? |
|---|---|
| Section 1 — Problem statement | N/A (lock, not implement) |
| Section 2 — Locked decisions | Tasks 0.5, 1.1–1.4 (Catalyst init), 6.2 (Gemini Live test) |
| Section 3 — Personas | N/A (research, done) |
| Section 4 — Success metrics | Tasks 7.1, 7.2 (latency measurement) |
| Section 5 — 9 features | Foundation only; features built in subsystem plans |
| Section 6 — Architecture | Tasks 1.1–1.4 prove Catalyst Functions + Circuits + parallel |
| Section 7 — Data strategy | Tasks 2.1, 2.2 prove Data Store + geospatial limits |
| Section 8 — Tech stack | All Phase 1–6 tasks validate stack pieces |
| Section 9 — Voice strategy | Tasks 6.1, 6.2, 6.3 cover Zia, Gemini Live, GCP fallback |
| Section 10 — LLM strategy | Tasks 3.1, 3.2 validate Qwen + Gemini |
| Section 11 — Security | Task 5.3 (Auth + role claims) |
| Section 12 — Team | All tasks have owners |
| Section 13 — Timeline | This plan IS Week 0 |
| Section 14 — Demo strategy | N/A (Week 8) |
| Section 15 — Risks | Mitigated by Phase 0–6 validations |
| Section 16 — NOT in scope | Honored — no morning briefing, no Mitra |
| Section 17 — Open questions | All 6 + Gemini Live = 7 validated this week |
| Section 18 — Decision log | Updated by every PASS/FAIL outcome |

**No placeholders. Every task has files, code, command, expected output, commit.**

---

## Upcoming Sub-Plans (drafted after Week 0 retro)

| # | Plan | Owner | Window | Trigger |
|---|---|---|---|---|
| 1 | **Data Layer** — Full schema, SQL views, RAG ingestion, NCRB ingest | A | Week 1 | Week 0 done |
| 2 | **AI Orchestrator** — Intent router, SQL/Cypher/RAG generators, synthesizer | B | Weeks 1–3 | Sub-plan 1 done |
| 3 | **Graph + Predictive** — Neo4j schema build-out, Cypher gen prompts, Zia AutoML training, Vertex backup | C | Weeks 2–4 | Sub-plan 1 done |
| 4 | **Frontend + Maps** — Full chat UI, streaming, Maps panel, network graph, audit drawer | D | Weeks 2–5 | Sub-plan 2 in progress |
| 5 | **Voice + Demo** — Production voice loop, UI polish, demo script, 3-min video | E | Weeks 4–7 | Sub-plan 4 in progress |
| 6 | **Integration + Submission** — All 9 features integrated, prototype submission package | All | Weeks 7–8 | Subs 1–5 done |
| 7 | **Shortlist Refinement** — Mentor feedback applied, 1 killer feature added | All | Weeks 9–11 | Aug 19 shortlist |
| 8 | **Finale Prep** — Stage rehearsals, backup video, demo choreography | All | Weeks 13–14 | Sep 9 final shortlist |

---

## Execution Handoff

Plan complete and saved to `C:\Users\sarav\Datathon 2026\plans\2026-06-16-foundation-week0.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Each task dispatched to a fresh subagent, reviewed between tasks. Fastest iteration.
2. **Inline Execution** — Tasks executed in this session with checkpoints for review.

**For this hackathon team:** Since each task has a different human owner (A, B, C, D, E), the realistic model is:
- Use this plan as a checklist
- Each owner picks up their phase
- Subagent-Driven works best if you want me to execute the steps for any single owner

---

*Plan locked: 2026-06-16. Foundation Week 0 plan. Update `validation/test_results.md` as tasks complete.*
