# Zoho Catalyst — Reference for KSP Saathi

> India console: https://console.catalyst.zoho.in
> India API base: https://api.catalyst.zoho.in
> Auth base (India): https://accounts.zoho.in
> Project ID format: 11-digit numeric (example seen in docs: `4000000006007`)
> Compiled: 2026-06-16 from official docs at https://docs.catalyst.zoho.com/en/

---

## 1. Service Overview

Catalyst is organized into four pillars: **Serverless**, **Cloud Scale**, **Zia Services**, and **Integrations**. The components below are what the official landing page surfaces.

| Service | One-liner |
|---|---|
| **Functions** (Serverless) | FaaS — Basic I/O, Advanced I/O, Event, Cron, Integration functions in Java/Node.js/Python |
| **Circuits** (Serverless) | JSON-defined workflow orchestrator that chains Basic I/O functions sequentially/concurrently |
| **Web Client Hosting / Slate** | Static + JS-framework hosting with custom domains |
| **Pipelines** (Serverless) | CI/CD for cross-environment deploys |
| **Data Store** (Cloud Scale) | Managed relational DB with ZCQL (SQL subset) |
| **NoSQL** (Cloud Scale) | Document store, JSON-shaped, write-heavy |
| **ZCQL** (Cloud Scale) | MySQL-like query language layered on Data Store |
| **Authentication** (Cloud Scale) | User management, hosted/embedded/third-party login, OAuth, roles |
| **File Store** (Cloud Scale) | Cloud storage; being replaced by Stratus (object storage, Early Access) |
| **Stratus** (Cloud Scale) | New object storage component, S3-like |
| **Cache** (Cloud Scale) | Key-value caching |
| **Cron** (Cloud Scale) | Scheduled function triggers |
| **Signals** (Cloud Scale) | Event Bus for event-driven architecture |
| **Connections** | Managed external service connections |
| **Job Scheduling** | Background job pool for functions, circuits, webhooks |
| **Zia OCR** | Text extraction; **11 Indian languages incl. Kannada** + 8 international |
| **Zia Face Analytics** | Face detection + attribute prediction |
| **Zia Object Recognition** | Object detection/classification in images |
| **Zia Identity Scanner** | Aadhaar/ID validation |
| **Zia Image Moderation** | NSFW detection |
| **Zia Text Analytics** | Sentiment, NER, keyword extraction |
| **Zia Barcode Scanner** | Universal barcode decoding |
| **QuickML** (Integrations) | No-code ML pipeline builder + **LLM Serving** (Qwen 2.5 family) + **RAG** |
| **SmartBrowz** | Headless browser → PDF/screenshot generation, HTML templates |
| **ConvoKraft** | Conversational bot assistant (chatbot framework) |
| **DevOps / APM / Logs** | Monitoring, application performance metrics, logs |

**SDKs:** Java, Node.js (v2), Python (v1), Web (browser), Android, iOS, Flutter + REST API + CLI.

**No native Speech-to-Text or Text-to-Speech.** `[CRITICAL — confirmed: Zia service list contains zero STT/TTS components.]` Voice will have to come from a third-party (Bhashini, Google, Sarvam, AWS) called from a Function.

[source: https://docs.catalyst.zoho.com/en/]

---

## 2. Catalyst CLI (zcatalyst-cli)

[source: https://docs.catalyst.zoho.com/en/cli/v1/cli-command-reference/]

### Install

`[UNCERTAIN — install page returned 404; standard install per Catalyst community is via npm.]`

```bash
npm install -g zcatalyst-cli
catalyst --version
```

### Authentication

| Command | What it does | Example |
|---|---|---|
| `catalyst login` | Browser OAuth login to your Catalyst account | `catalyst login` |
| `catalyst logout` | Sign out | `catalyst logout` |
| `catalyst whoami` | Show current authenticated email | `catalyst whoami` |
| `catalyst token:generate` | Create a long-lived CLI token (for CI/CD) | `catalyst token:generate --name ksp-ci` |
| `catalyst token:list` | List generated tokens | `catalyst token:list` |
| `catalyst token:revoke <id>` | Revoke a token (must be on same device) | `catalyst token:revoke 12345` |

> Tokens never expire unless revoked, and are bound to one data center. Use for CI; rotate manually.

### Project lifecycle

| Command | What it does | Example |
|---|---|---|
| `catalyst init` | Scaffold a new project (interactive) | `catalyst init` |
| `catalyst project:list` | List projects on your account | `catalyst project:list` |
| `catalyst project:use <id_or_name>` | Bind the current dir to a project | `catalyst project:use 4000000006007` |
| `catalyst project:reset` | Clear project binding | `catalyst project:reset` |

### Functions

| Command | What it does | Example |
|---|---|---|
| `catalyst functions:setup` | Configure the `functions/` directory | `catalyst functions:setup` |
| `catalyst functions:add` | Scaffold a new function (prompts for type + runtime) | `catalyst functions:add` |
| `catalyst functions:config` | Adjust memory/timeout for a function | `catalyst functions:config saathi-chat` |
| `catalyst functions:shell` | Interactive REPL to invoke functions locally | `catalyst functions:shell` |
| `catalyst functions:delete` | Remove a function | `catalyst functions:delete saathi-chat` |
| `catalyst event:generate <source> <action>` | Emit a fake event payload for testing | `catalyst event:generate datastore insert` |

### Dev + deploy

| Command | What it does | Example |
|---|---|---|
| `catalyst serve` | Run functions + client locally | `catalyst serve` |
| `catalyst deploy` | Push all resources to remote | `catalyst deploy` |
| `catalyst deploy --only functions` | Deploy only functions (faster) | `catalyst deploy --only functions:saathi-chat` |
| `catalyst pull` | Sync remote → local | `catalyst pull functions` |

### Data Store I/O

| Command | What it does | Example |
|---|---|---|
| `catalyst ds:import <file.csv>` | Bulk-load rows from CSV | `catalyst ds:import cases.csv --table cases` |
| `catalyst ds:export` | Export rows to CSV | `catalyst ds:export --table cases` |
| `catalyst ds:status <op> <job_id>` | Check status of bulk op | `catalyst ds:status import 9988` |

### Config

| Command | Example |
|---|---|
| `catalyst config:set key=value` | `catalyst config:set GEMINI_KEY=xxx` |
| `catalyst config:get key` | `catalyst config:get GEMINI_KEY` |
| `catalyst config:list` | `catalyst config:list` |

---

## 3. Python SDK (zcatalyst_sdk)

[source: https://docs.catalyst.zoho.com/en/sdk/python/v1/overview/, https://docs.catalyst.zoho.com/en/sdk/python/v1/setup/]

### Install

```bash
pip install zcatalyst-sdk
```

**Required Python version: 3.10 – 3.13.** Functions outside this range are skipped at deploy.

### Initialize (per function type)

```python
# Basic I/O
import zcatalyst_sdk
def handler(context, basicio):
    app = zcatalyst_sdk.initialize()
    # ... app.datastore(), app.zia(), etc.

# Advanced I/O (Flask-like request/response)
import zcatalyst_sdk
def handler(request):
    app = zcatalyst_sdk.initialize()
    return {"ok": True}

# Event
def handler(event, context):
    app = zcatalyst_sdk.initialize()

# Cron
def handler(cron_details, context):
    app = zcatalyst_sdk.initialize()
```

### Scope (admin vs end-user)

```python
app = zcatalyst_sdk.initialize(scope='admin')  # default — bypasses table ACLs
app = zcatalyst_sdk.initialize(scope='user')   # uses caller's JWT permissions
```

### Components available on `app`

```python
app.datastore()    # relational DB
app.zcql()         # SQL-ish queries against Data Store
app.nosql()        # document DB
app.cache()        # k/v cache
app.file_store()   # blob/file storage
app.stratus()      # object storage (S3-like, EA)
app.user_management()  # auth users
app.zia()          # OCR/Vision/Text Analytics
app.smart_browz()  # PDF/screenshot
app.quick_ml()     # ML endpoints + LLM Serving
app.circuit()      # trigger circuits
app.connection()   # external service connections
```

### Data Store CRUD (typical pattern)

`[UNCERTAIN — sub-pages 404'd, code below is the canonical SDK pattern from the OCR page and SDK overview.]`

```python
app = zcatalyst_sdk.initialize()
ds  = app.datastore()
table = ds.table('cases')

# Insert
row = table.insert_row({'case_number': 'KA001234', 'status': 'OPEN'})

# Get one
row = table.get_row(row_id)

# Update
table.update_row({'ROWID': row_id, 'status': 'CLOSED'})

# Delete
table.delete_row(row_id)

# Bulk
table.insert_rows([{...}, {...}])
```

### ZCQL query

```python
zcql = app.zcql()
rows = zcql.execute_zcql_query(
    "SELECT case_number, status FROM cases "
    "WHERE district = 'Bengaluru Urban' ORDER BY CREATEDTIME DESC LIMIT 50"
)
```

### Call another function

```python
fn = app.function('summarize')
result = fn.execute({"text": "..."})
```

### Zia OCR

```python
zia = app.zia()
with open('fir.pdf', 'rb') as f:
    result = zia.extract_optical_characters(
        f, {"language": "eng", "modelType": "OCR"}
    )
# result: {"confidence": 95, "text": "..."}
```

### SmartBrowz PDF

```python
sb = app.smart_browz()
sb.convert_to_pdf(source='<html><body>...</body></html>')
sb.generate_output_from_template(template_id='TPL123', output_type='pdf')
sb.take_screenshot(source='https://example.com',
                   page_options={'device': 'iphone 13 pro'})
```

---

## 4. Data Store

[source: https://docs.catalyst.zoho.com/en/cloud-scale/help/data-store/introduction/, https://docs.catalyst.zoho.com/en/cloud-scale/help/zcql/introduction/]

- **Model:** Relational. Tables → columns → rows. Each row gets `ROWID`, `CREATEDTIME`, `MODIFIEDTIME` system columns.
- **Query language:** **ZCQL** — MySQL-flavoured. Supports `SELECT / INSERT / UPDATE / DELETE`, `WHERE`, `HAVING`, `JOIN`, `GROUP BY`, `ORDER BY`, `LIMIT`, plus built-in arithmetic/numeric functions.
- **Bulk ops:** Bulk Read / Bulk Write / Bulk Delete. Bulk writes go through a background queue — track via `catalyst ds:status`.
- **OLAP:** Built-in OLAP engine for analytical queries at any scale.
- **Search:** Indexed columns are searchable via Catalyst Search.
- **ACL:** Per-table scopes/permissions tied to user roles.
- **Migration note:** ZCQL **V2 parser** became default from December 1, 2024 in dev. Test legacy queries.

### CSV import via CLI

```bash
catalyst ds:import data/cases.csv --table cases
catalyst ds:status import <job_id>
```

`[UNCERTAIN — exact data type list (TEXT/BIGINT/DATETIME/BOOLEAN/etc.) not in fetched pages; verify in console schema editor.]`

---

## 5. NoSQL

[source: https://docs.catalyst.zoho.com/en/cloud-scale/help/nosql/introduction/]

- **Model:** Document / key-value with JSON-typed values. No fixed schema.
- **Scaling:** Horizontal + vertical, peer-to-peer replication across clusters (partition keys for sharding).
- **Indexing:** Secondary indexes configurable per attribute.
- **Best for:** Write-heavy workloads, unstructured/semi-structured payloads (chat logs, audit trails, raw event data).
- **Avoid for:** Strong-consistency / multi-row transactional work — that's Data Store's job.
- **Access:** Java/Node/Python SDK, REST API, console.
- **Migration:** Tooling exists for importing from third-party NoSQL DBs.

**Rule of thumb for KSP Saathi:** transcripts, intermediate chat state, vector chunks → NoSQL. Officer profiles, case rows, audit ledger → Data Store.

---

## 6. Authentication

[source: https://docs.catalyst.zoho.com/en/cloud-scale/help/authentication/introduction/, https://docs.catalyst.zoho.com/en/api/introduction/overview-and-prerequisites/]

### Modes (one of each per app)

1. **Native Catalyst Auth** — Hosted (Catalyst-hosted login page) or Embedded (your own UI calls the SDK).
2. **Third-party** — bring your own IdP (Google, Zoho, custom SAML/OAuth).

### Features

- Email/password + social login (Google, Zoho documented; others via third-party mode)
- Customizable login/signup forms + email templates (invite, reset)
- Role-based access control — roles defined per project, applied on tables/functions
- Domain authorization with CORS + iFrame whitelisting

### OAuth 2.0 (for API access)

- Register at https://api-console.zoho.com/
- Grant token (60-second TTL) → exchanged for access + refresh tokens
- Access token sent as: `Authorization: Zoho-oauthtoken {access_token}`
- India auth endpoint: `https://accounts.zoho.in/oauth/v2/token`

### JWT structure

`[UNCERTAIN — Catalyst docs don't publish the exact claim layout; observed in practice it includes ROWID, email, role_id, project_id, exp, iat. Verify by decoding a real token at https://jwt.io after embedded login.]`

### Verifying caller in a Function

Initialize the SDK with user scope and read the calling user:

```python
app  = zcatalyst_sdk.initialize(scope='user')
um   = app.user_management()
me   = um.get_current_user()
# me.role.name, me.email_id, me.user_id
```

---

## 7. Functions (Serverless)

[source: https://docs.catalyst.zoho.com/en/serverless/help/functions/introduction/]

### Five types

| Type | Trigger | Notes |
|---|---|---|
| **Basic I/O** | HTTP GET with query params; returns string | Only type usable inside Circuits |
| **Advanced I/O** | Full HTTP (any method, headers, body) | Returns native HTTP response; **cannot run locally** before deploy |
| **Event** | Catalyst event listener (DataStore insert, Auth signup, etc.) | Async, no response to caller |
| **Cron** | Time-based schedule | One-off or recurring |
| **Integration** | Triggered by other Zoho service hooks | **Not available in India DC** |

### Limits

- **Execution time:** 30 seconds (Basic + Advanced I/O). `[UNCERTAIN — longer for Cron/Event; not stated in fetched page.]`
- **Memory:** configurable via `catalyst functions:config`.
- **Runtimes:** Java, Node.js, Python (3.10–3.13).

### Folder layout (CLI-initialized)

```
project-root/
  catalyst.json                 # project meta
  functions/
    saathi-chat/
      catalyst-config.json      # function manifest
      main.py                   # entry point
      requirements.txt
  client/                       # web client hosting
  data_store/                   # schema dumps
```

### `catalyst-config.json` (minimal Python advanced-io)

`[UNCERTAIN — exact field set not in fetched pages; typical shape:]`

```json
{
  "deployment": {
    "name": "saathi-chat",
    "main": "main.handler",
    "memory": 256,
    "timeout": 30,
    "stack": "python3.11"
  },
  "execution": {
    "type": "AdvancedIO"
  }
}
```

### Advanced I/O Python skeleton

```python
import zcatalyst_sdk
from werkzeug.wrappers import Request, Response

def handler(request: Request):
    app = zcatalyst_sdk.initialize()
    body = request.get_json(silent=True) or {}
    # ... do work ...
    return Response('{"ok": true}', mimetype='application/json')
```

### Environment variables

Set via `catalyst config:set` or in the console. Read in Python with `os.environ['KEY']`.

---

## 8. Circuits (Workflow)

[source: https://docs.catalyst.zoho.com/en/serverless/help/circuits/introduction/]

### What it is

A circuit is a JSON workflow definition that chains **Basic I/O functions** sequentially or concurrently, with conditionals, data passing, and retries.

### CRITICAL availability gotcha

> **Circuits is NOT available in the IN, EU, AU, JP, SA, or CA data centers.**

This is the single biggest architectural constraint for KSP Saathi. Since the project must run in the India DC, **we cannot use Circuits**. Workflow orchestration has to be done one of:

- In-function Python control flow (call sub-functions sequentially with `app.function('x').execute(...)`)
- Catalyst Signals (event bus) as a poor-man's pub/sub
- External orchestrator (Temporal, n8n) hosted elsewhere — undesirable

### If we ever deploy outside India

- Build via console drag-drop or hand-write JSON
- Trigger: manual, REST, or SDK (`app.circuit().execute_circuit(...)`)
- Input/output must be JSON (Basic I/O constraint)
- Cron/Event/Advanced I/O functions cannot participate

---

## 9. Zia Services

[source: https://docs.catalyst.zoho.com/en/zia-services/, https://docs.catalyst.zoho.com/en/zia-services/help/optical-character-recognition/key-concepts/]

### Inventory

| Service | What it does | Key facts |
|---|---|---|
| **OCR** | Text from images/PDFs | 19 langs total |
| **Face Analytics** | Face detection + attributes | — |
| **Object Recognition** | Multi-object detection | — |
| **Identity Scanner** | Aadhaar/PAN/passport validation | Needs ID lang + English (e.g. `tam`+`eng`) |
| **Image Moderation** | NSFW classifier | — |
| **Barcode Scanner** | Universal barcodes | — |
| **Text Analytics** | Sentiment, NER, keyword extraction | — |

### OCR languages (confirmed list)

**Indian (11):** English, Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu, **Kannada**, Malayalam, Sanskrit.

**International (8):** Arabic, Chinese, French, Italian, Japanese, Portuguese, Romanian, Spanish.

> **CRITICAL: Kannada IS supported by Zia OCR.** Auto-detection works when language is omitted.

### File limits

- Formats: JPG, JPEG, PNG, TIFF, BMP, PDF
- Max file size: **20 MB**

### Python usage

```python
zia = app.zia()
result = zia.extract_optical_characters(
    open('aadhaar.jpg', 'rb'),
    {"language": "eng", "modelType": "OCR"}
)
# {"confidence": 95, "text": "..."}
```

### What's MISSING (critical for KSP Saathi)

**No Speech-to-Text. No Text-to-Speech. No native LLM (other than via QuickML).** All voice + chat-LLM work needs an external provider.

---

## 10. QuickML — LLM Serving + RAG

[source: https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/llm-serving/, https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/rag/, https://docs.catalyst.zoho.com/en/quickml/help/pipeline-endpoints/]

### Available models (LLM Serving)

| Model | Params | Trained on | Context | Use case |
|---|---|---|---|---|
| **Qwen 2.5 — 14B Instruct** | 14 B | 18 T tokens | **128 K** | General chat / instruction |
| **Qwen 2.5 — 7B Coder** | 7 B | 5.5 T tokens | (Smaller) | Code generation |
| **Qwen 2.5 — 7B Vision Language** | 7 B | — | — | Multimodal (image+text) |

### Region availability

> Available in **US, IN, EU** data centers. Good — India works.

### Custom model upload

`[UNCERTAIN — fetched pages don't explicitly say custom LLM upload is supported. Pipeline endpoints support custom ML models; LLM Serving appears limited to the three Qwen models.]`

### Authentication + endpoint

- Headers:
  - `X-QUICKML-ENDPOINT-KEY: <endpoint-key>`
  - `Authorization: Zoho-oauthtoken <access-token>`
  - `CATALYST-ORG: <org-id>`
  - `Environment: Development|Production`
- HTTP: `POST` only
- OAuth scope: `QuickML.deployment.READ`

### Parameters (LLM Serving)

- `temperature` — 0.0–1.0
- `top_k`, `top_p`
- `max_tokens` — 1–4096
- `instructions` — system prompt

### Inference (Python)

```python
import requests

endpoint = "https://api.catalyst.zoho.in/.../quickml/endpoints/<id>"
headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}",
    "X-QUICKML-ENDPOINT-KEY": endpoint_key,
    "CATALYST-ORG": org_id,
    "Environment": "Production",
    "Content-Type": "application/json",
}
body = {
    "prompt": "List the steps to file an FIR.",
    "temperature": 0.3,
    "max_tokens": 1024,
}
resp = requests.post(endpoint, json=body, headers=headers, timeout=60)
print(resp.json())
```

### RAG

- Uses **Qwen 2.5-14B-Instruct** as the generator
- Knowledge base: PDF, DOCX, TXT — **500 KB max per file**
- Can import directly from Zoho WorkDrive / Zoho Learn
- Returns answer + citations (source doc + section)
- Auth: same OAuth scope `QuickML.deployment.READ`

### Streaming

`[UNCERTAIN — streaming SSE not documented for QuickML LLM endpoints in fetched pages; assume non-streaming JSON until verified.]`

---

## 11. SmartBrowz (PDF Generation)

[source: https://docs.catalyst.zoho.com/en/smartbrowz/help/pdfnscreenshot/implementation/]

### Capabilities

- Render any URL or HTML string → PDF / screenshot
- Use stored HTML+CSS templates with JSON placeholders for dynamic data
- Password-protect output PDFs
- Device emulation (iPhone, iPad) for responsive screenshots

### Python SDK

```python
sb = app.smart_browz()

# HTML → PDF
sb.convert_to_pdf(source='<html>...</html>')

# Template + data → PDF
sb.generate_output_from_template(
    template_id='TPL_FIR_RECEIPT',
    output_type='pdf',
    # placeholder data goes in this call's options dict
)

# URL → screenshot
sb.take_screenshot(
    source='https://ksp.gov.in/case/12345',
    page_options={'device': 'iphone 13 pro'}
)
```

### Font support (Kannada?)

> **`[UNCERTAIN]`** SmartBrowz docs do not mention Indic / Kannada font availability. Since it's a Chromium-based headless browser, fonts must be either system-installed or embedded in HTML via `@font-face`. **Safe approach:** bundle Noto Sans Kannada as a base64 `@font-face` block inside the HTML template.

---

## 12. Web Client Hosting

`[UNCERTAIN — introduction page returned 404 at multiple paths; what follows is from the platform overview + community knowledge.]`

- Hosts static sites + JS frameworks (React, Vue, Angular, Next.js export) under the **Catalyst Slate** brand
- Auto-builds on `catalyst deploy`
- Custom domains supported (DNS CNAME to Catalyst)
- Client lives in `client/` directory of the project

[source: https://docs.catalyst.zoho.com/en/]

---

## 13. Integrations — OpenAI / Gemini patterns

[source: https://docs.catalyst.zoho.com/en/integrations/openai-integration/introduction/]

The native "OpenAI integration" inside Catalyst is **dev-tooling only** — it powers the Zia AI Assistant (code generator, converter, debugger inside the console). It is **not** a runtime LLM service we can call from a Function.

### Implications for KSP Saathi (Gemini)

Catalyst gives us no native bridge to Gemini. We will:

1. Store the Gemini API key in `catalyst config:set GEMINI_KEY=...` (becomes an env var).
2. Inside an Advanced I/O Python function, call Gemini via the `google-generativeai` SDK:

```python
import os, google.generativeai as genai
genai.configure(api_key=os.environ['GEMINI_KEY'])
model = genai.GenerativeModel('gemini-2.0-flash')
resp  = model.generate_content("...")
```

3. BYOK is the same model Catalyst uses for its own OpenAI integration — sensitive data **does leave the data center** when calling Gemini. Note this for the Karnataka State Police data-residency review.

---

## 14. REST API

[source: https://docs.catalyst.zoho.com/en/api/introduction/overview-and-prerequisites/]

### Base URL (India)

```
https://api.catalyst.zoho.in/baas/v1/project/{project_id}/{resource}/{...}
```

### Required headers

```
Authorization: Zoho-oauthtoken {access_token}
Content-Type:  application/json
```

### Optional headers

```
CATALYST-ORG: {org_id}
Environment:  Development | Production
```

### Common scopes

```
ZohoCatalyst.tables.rows.READ
ZohoCatalyst.tables.rows.CREATE
ZohoCatalyst.functions.EXECUTE
ZohoCatalyst.files.CREATE
QuickML.deployment.READ
```

### Standard error codes

- `400` INVALID_INPUT
- `401` UNAUTHORISED
- `403` INVALID_OPERATION
- `404` INVALID_ID

### Sample call

```bash
curl -X POST \
  "https://api.catalyst.zoho.in/baas/v1/project/4000000006007/table/cases/row" \
  -H "Authorization: Zoho-oauthtoken $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"case_number":"KA001234","status":"OPEN"}'
```

### Standard response shape

```json
{ "status": "success", "data": { /* resource */ } }
```

---

## 15. Common Recipes

### 15.1 Insert a Data Store row from a Python function

```python
import zcatalyst_sdk

def handler(request):
    app = zcatalyst_sdk.initialize()
    case = request.get_json()
    row  = app.datastore().table('cases').insert_row({
        'case_number': case['case_number'],
        'complainant': case['name'],
        'district':    case['district'],
        'status':      'OPEN',
    })
    return {"ok": True, "row_id": row['ROWID']}
```

### 15.2 Call a Function from a Function

```python
app = zcatalyst_sdk.initialize()
summarized = app.function('summarize').execute({"text": long_text})
```

### 15.3 Query Data Store via ZCQL

```python
rows = app.zcql().execute_zcql_query(
    "SELECT case_number, status FROM cases "
    "WHERE district = 'Bengaluru Urban' "
    "AND CREATEDTIME > '2026-06-01' "
    "ORDER BY CREATEDTIME DESC LIMIT 25"
)
```

### 15.4 Call QuickML LLM (Qwen 2.5-14B-Instruct) from a function

```python
import os, requests
endpoint = os.environ['QWEN_ENDPOINT']
key      = os.environ['QWEN_ENDPOINT_KEY']
token    = os.environ['ZOHO_OAUTH_TOKEN']

r = requests.post(endpoint,
    headers={
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-QUICKML-ENDPOINT-KEY": key,
        "CATALYST-ORG": os.environ['CATALYST_ORG'],
        "Environment": "Production",
        "Content-Type": "application/json",
    },
    json={
        "prompt": "Translate to Kannada: ...",
        "temperature": 0.2,
        "max_tokens": 2048,
    },
    timeout=30,
)
print(r.json())
```

### 15.5 OCR a Kannada FIR scan

```python
zia = zcatalyst_sdk.initialize().zia()
with open('fir_kn.jpg', 'rb') as f:
    out = zia.extract_optical_characters(
        f, {"language": "kan", "modelType": "OCR"}
    )
# `[UNCERTAIN — language code "kan" is the ISO 639-2 standard;
#   Zoho's exact code may differ. Verify against console-displayed code.]`
```

### 15.6 Generate a PDF receipt with Kannada text

```python
html = """
<html><head>
  <style>
    @font-face {
      font-family: 'NotoKn';
      src: url('data:font/woff2;base64,<...base64-NotoSansKannada...>') format('woff2');
    }
    body { font-family: 'NotoKn', sans-serif; }
  </style>
</head><body>
  <h1>ಪ್ರಥಮ ವರ್ತಮಾನ ವರದಿ</h1>
  <p>ಪ್ರಕರಣ ಸಂಖ್ಯೆ: KA001234</p>
</body></html>
"""
pdf = zcatalyst_sdk.initialize().smart_browz().convert_to_pdf(source=html)
```

### 15.7 Verify a user's role in a Function

```python
app = zcatalyst_sdk.initialize(scope='user')
me  = app.user_management().get_current_user()
if me.role.name != 'investigating_officer':
    return {"error": "forbidden"}, 403
```

---

## 16. Gotchas + Limits

1. **No Circuits in India DC.** This is the single biggest constraint. All orchestration has to be in-Python or via Catalyst Signals. Plan accordingly. [source: https://docs.catalyst.zoho.com/en/serverless/help/circuits/introduction/]

2. **No native STT / TTS.** Zia has zero voice services. Bhashini, Sarvam, Google, or Azure must be wired in via direct HTTPS calls from a Function. Data leaves the Catalyst boundary when you do this.

3. **30-second function timeout** on Basic + Advanced I/O. Any long Gemini call risks timeout — use streaming on the client or break into Cron jobs.

4. **Python 3.10–3.13 only.** 3.9 and 3.14 functions get silently skipped at deploy.

5. **Integration Functions unavailable in India DC.** Same regional gap as Circuits.

6. **OCR file limit: 20 MB.** Multi-page FIR scans may need chunking.

7. **RAG knowledge-base file limit: 500 KB each.** Large case files must be split / pre-summarized.

8. **File Store dev limit: 1 GB.** Production is unlimited, but plan for the dev cap during the datathon.

9. **Stratus (new object store) is Early Access only.** Default to File Store for now; email `support@zohocatalyst.com` if Stratus access is needed.

10. **CLI tokens never expire and are bound to one DC.** Treat them like long-lived secrets; rotate manually before handover.

11. **ZCQL V2 parser is default since Dec 2024.** If you copy ZCQL from a tutorial older than that, verify it still parses.

12. **OpenAI integration is dev-tooling only**, not a runtime LLM endpoint. Don't plan around it.

13. **`scope='admin'` bypasses table ACLs.** Use `scope='user'` whenever the function acts on behalf of an end user; admin scope is for system-of-record / migration work.

14. **Indic font support in SmartBrowz is undocumented.** Embed Noto Sans Kannada via `@font-face` base64 — don't rely on system fonts.

15. **Project ID is 11-digit numeric**, not the slug shown in the console URL. Use the numeric ID in API calls and CLI commands.

16. **India accounts auth domain is `accounts.zoho.in`**, not `accounts.zoho.com`. Hitting the wrong domain produces opaque 401s.

17. **Custom JWT claims** are not documented as a first-class feature. Role checks must be done server-side via `app.user_management().get_current_user()` rather than trusting client-sent JWT claims.

18. **BYOK for external LLMs.** Any Gemini/OpenAI call from a Function means prompts leave the Catalyst data center. Document this for the KSP compliance review.
