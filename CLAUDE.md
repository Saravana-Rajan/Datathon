# Sarvik (ಸರ್ವಿಕ್) — Datathon 2026 Project Context

> **Product name:** **Sarvik** — from Sanskrit *sarvika* meaning "comprehensive / all-encompassing". The investigator's universal companion across all crime data.
> **Catalyst project name:** `Sarvik` (PID `47060000000020024` — India DC) ✅ active
> **Previous names (do not use):** Yakshna · Yaksha · KSP Saathi
> **Internal codename:** `ksp-saathi` (kept for code identifiers / folder names / function IDs — do NOT rename code paths, it breaks everything)

> This file is auto-loaded into every Claude Code session. Read it before doing anything.

---

## What this project is

**Sarvik** (codename `ksp-saathi`) = conversational AI for Karnataka State Police investigators. **Datathon 2026 Challenge 01** entry. Win goal: ₹2.5L (1st place). Finale demo day: 26 Sep 2026 in-person.

All product decisions are locked in [`design.md`](./design.md) — **don't re-litigate them**, only update via Section 18 Decision Log.

---

## User profile (Saravana Rajan)

- Email: `saravanarajan.b@techjays.com`
- Catalyst account: User ID `60067540097`, Org `60074155874`, India console (`console.catalyst.zoho.in`)
- **Catalyst project: `Sarvik`** — PID `47060000000020024` (active, India DC)
- **Console URL:** https://console.catalyst.zoho.in/baas/60074155874/project/47060000000020024/Development
- **Previous project (deprecated):** `47060000000020001` (was `Yakshna`)
- Catalyst credits: **claimed** ✅ (promo code `KSPH26`)
- Role on this project: monitors progress; delegates implementation to Claude
- Communication style: short, decisive, prefers ALL CAPS for emphasis when frustrated
- Wants speed, parallel agents, minimal back-and-forth confirmation
- Has full GCP access (Gemini, Maps, Vertex AI)
- Comfortable swapping tools mid-build when better options appear

## Working norms (do these, don't ask)

1. **Auto mode is on.** Make the reasonable call, keep going. Only stop when truly blocked or a user-only decision is needed.
2. **Use parallel background agents aggressively** — up to 20+ at once if work is independent. User explicitly authorized "70 background tasks if needed".
3. **Don't ask for confirmation on locked decisions.** They're in `design.md` Section 18.
4. **Don't propose pivots that deviate from the official problem statement.** The "Mitra morning briefing" idea was REJECTED — stay in scope.
5. **Don't propose predictive policing in Minority Report framing.** Predictions are "resource hints" only. Bias-safe by design.
6. **Write code, not just plans.** User wants implementation, not endless planning.
7. **Don't recommend Sarvam.ai** — replaced by Gemini Live API (see Decision Log 2026-06-16).
8. **Don't ask "should I proceed?"** — just proceed and surface results.

---

## The locked tech stack

```
PLATFORM:  Zoho Catalyst (mandatory, primary, ~90% of stack)
AUGMENT:   Google Cloud (Gemini Live API, Gemini 2.5 Pro, Maps, embeddings)
GRAPH:     Neo4j AuraDB Free
REGION:    asia-south1 (Mumbai) + Catalyst India DC — IT Act 2008 compliant
COST:      ₹0 (free credits everywhere)
```

### Catalyst services in use
Web Client Hosting · Domain Mappings · Authentication · Functions · Circuits · API Gateway · Data Store · NoSQL · Stratus · Cache · QuickML LLM Serving (Qwen 2.5 14B) · QuickML RAG · Zia AutoML · Zia Services (English/Hindi voice ONLY — no Kannada) · SmartBrowz · Cron · Mail · Push · Signals · Event Functions · Pipelines

### Google services in use (justified gaps)
- **Gemini Live API** (`gemini-live-2.5-flash-preview` / `gemini-live-3.5-translate`) — Kannada voice STT+TTS in one streaming call. Catalyst Zia has no Kannada.
- **Gemini 2.5 Pro** — premium Kannada synthesis when Qwen quality insufficient
- **`gemini-embedding-001`** — multilingual RAG embeddings (Kannada + English)
- **Google Maps Platform** — Catalyst has no Maps service
- **Neo4j AuraDB Free** — Catalyst has no graph DB

### ON HOLD (do not build unless explicitly told)
- **Vertex AI Forecasting** — paused. Instructions in `docs/vertex-ai-forecasting-todo.md`. Catalyst Zia AutoML is primary for forecasting.

---

## The 9 features (Challenge 01 problem statement — all in scope, no cuts)

1. Natural language chatbot (English + Kannada)
2. Voice-enabled interaction
3. Context-aware conversations
4. PDF export of conversation history
5. Criminal network visualization
6. Crime trend & hotspot detection
7. Predictive analytics & early warnings *(Zia AutoML primary, Vertex on hold)*
8. Explainable AI with audit trails
9. Role-based secure access

**Do not add features outside this list. Do not remove any.**

---

## File layout

```
C:\Users\sarav\Datathon 2026\
├── CLAUDE.md                          ← this file (auto-loaded)
├── README.md                          ← project overview
├── design.md                          ← LOCKED design doc — single source of truth
├── decisions.md                       ← justification log for every Google service
├── validation-checklist.md            ← Week 0 validations per teammate
├── email-organizers.md                ← draft email to hack2skill
├── challenges.md, timeline.md, rewards.md, faqs.md, terms-and-conditions.md
│                                        (official hackathon docs)
├── research-investigators.md          ← CCTNS pain points, personas, top queries
├── research-catalyst.md               ← Catalyst service capabilities + gaps
├── data/
│   ├── generate_synthetic_firs.py     ← FIR generator (DONE)
│   ├── firs.jsonl                     ← 50K synthetic FIRs (DONE)
│   ├── firs_sample.jsonl              ← first 100 for testing
│   └── README.md
├── docs/                              ← external doc references for offline lookup
│   ├── catalyst-reference.md          ← Zoho Catalyst docs harvested
│   ├── gemini-live-reference.md       ← Gemini Live API harvested
│   ├── gemini-embeddings-reference.md ← Gemini embeddings harvested
│   └── vertex-ai-forecasting-todo.md  ← on-hold instructions
├── plans/
│   └── 2026-06-16-foundation-week0.md ← Week 0 implementation plan
└── app/
    ├── backend/                       ← Catalyst project (Functions, Circuits)
    │   ├── catalyst.json
    │   ├── functions/
    │   │   ├── hello/
    │   │   ├── intent-router/
    │   │   ├── sql-generator/
    │   │   ├── cypher-generator/
    │   │   ├── rag-retriever/
    │   │   ├── synthesizer/
    │   │   ├── audit-logger/
    │   │   └── pdf-exporter/
    │   ├── circuits/
    │   │   └── main-query-flow.yaml
    │   └── shared/                    ← shared Python utils (gemini client, etc.)
    ├── frontend/                      ← Next.js 15 app
    │   ├── package.json
    │   ├── next.config.js
    │   ├── catalyst.json
    │   ├── src/
    │   │   ├── app/
    │   │   ├── components/
    │   │   │   ├── ChatPanel.tsx
    │   │   │   ├── VoiceRecorder.tsx
    │   │   │   ├── MapPanel.tsx
    │   │   │   ├── NetworkGraph.tsx
    │   │   │   ├── AuditDrawer.tsx
    │   │   │   ├── LanguageToggle.tsx
    │   │   │   └── AuthGate.tsx
    │   │   └── lib/
    │   └── public/
    ├── data-pipeline/                 ← ingestion scripts
    │   ├── jsonl_to_catalyst.py       ← upload FIRs to Data Store
    │   ├── neo4j_ingest.py            ← build criminal network graph
    │   ├── embed_narratives.py        ← Gemini embeddings batch
    │   └── h3_hotspot_index.py        ← H3 hex indexing
    └── validation/                    ← Week 0 test scripts
        ├── test_catalyst_zia_voice.py
        ├── test_gemini_live_kannada.py
        ├── test_qwen_kannada_quality.py
        ├── test_data_store_geospatial.py
        ├── test_zia_automl_forecast.py
        ├── test_circuits_parallel.py
        └── test_results.md
```

---

## What to do in a new session

1. **Read `design.md`** — locked plan, 20 sections
2. **Read `decisions.md`** — every third-party service is justified there
3. **Check `plans/`** — see which sub-plan is active
4. **Check task tracker** (`TaskList`) — see what's in-progress
5. **Don't re-ask** locked decisions — append to Decision Log if changing

## Catalyst gotchas (HARD-WON, do not re-discover)

These were learned the painful way during the first deploy. **Stick to these literals exactly.**

### catalyst-config.json schema (per-function)
```json
{
  "deployment": {
    "name": "<function-name>",
    "type": "advancedio",         // lowercase, one word — NOT "AdvancedIO"
    "stack": "python_3_9",         // ONLY valid Python literal — NOT python311, NOT python3.11
    "memory": 256,
    "timeout": 10
  },
  "execution": {
    "main": "index.py"             // file NAME — NOT "index.handler"
  }
}
```

### Project-level catalyst.json schema (in app/backend/)
Functions need a `functions.targets` array (not `features.functions.enabled`):
```json
{
  "project_id": "47060000000020024",
  "functions": {
    "source": "functions",
    "targets": ["hello", "intent-router", "..."]
  }
}
```

### Python runtime facts
- **Catalyst Functions ONLY support Python 3.9** (not 3.10/3.11/3.12 — those work only in AppSail with `app-config.json`)
- Local Python 3.9 binary REQUIRED for CLI packaging:
  - Windows install: `winget install --id Python.Python.3.9 --silent`
  - Then: `catalyst config:set python3_9.bin=/c/Users/sarav/AppData/Local/Programs/Python/Python39/python.exe`
- CLI validates `python --version` output starts with `3.9` — can't spoof with 3.11

### Package version caps
- `zcatalyst-sdk` max version on PyPI = **1.3.0** (do NOT use `>=1.5.0` — it doesn't exist)
- `typing-extensions` cap = `~=4.12.1` (constrained by zcatalyst-sdk)

### Active deployment URLs (Sarvik)
All 9 functions live at: `https://sarvik-60074155874.development.catalystserverless.in/server/<function-name>/`
- hello · intent-router · sql-generator · cypher-generator · rag-retriever
- synthesizer · audit-logger · pdf-exporter · orchestrator

### CLI quirks
- `catalyst project:use <PID>` is silent — writes `.catalystrc` in cwd
- `catalyst deploy --only functions:hello` deploys one function
- `catalyst deploy --only functions` deploys ALL listed targets
- Transient pip failures happen — just retry the specific function
- All commands need `cd app/backend` first (or pass `-p Sarvik`)

### Basic I/O CANNOT return generators (learned 2026-06-17 — synthesizer + orchestrator both 500'd)
**Catalyst Basic I/O functions CANNOT return Python generators.** The runtime
attempts to JSON-serialise the return value and 500s the moment it hits an
iterator — there is no streaming-SSE escape hatch in this function type. The
old "yield SSE bytes from handler" pattern works locally with `b"".join(...)`
but fails the instant Catalyst dispatches the function.

**Workarounds (pick one):**
1. **Collect-and-return-once (what we did for synthesizer + orchestrator).**
   Buffer every SSE-shaped event into a list and return a single JSON payload:
   ```json
   {"ok": true, "request_id": "...", "events": [{"type":"text_chunk",...}, ...]}
   ```
   Consumers iterate `events` and replay them as if they were a closed SSE
   stream. Sacrifices token-by-token streaming but works on Basic I/O.
2. **Switch function `type` to `event`** (no HTTP response, fire-and-forget).
   Catalyst Signals / Cron triggers it. The user polls a result table for
   completion. Good fit for long-running audit / pipeline jobs.
3. **Switch function `type` to `job`** (long-running, results queried
   separately via a job-id). Best for forecasting / batch RAG re-indexing.

**Streaming SSE end-to-end requires AppSail** (full WSGI/ASGI server, not
Basic I/O). If the demo ever needs true progressive token rendering for
Kannada synthesis, promote the synthesizer to AppSail — but for the
current build, the collect-and-return pattern is enough because the
Next.js `/api/chat` BFF can still emit SSE to the browser by iterating
the buffered list and yielding one frame per event.

## What to NOT do

- ❌ Don't mention Sarvam.ai as a recommendation (replaced by Gemini Live API)
- ❌ Don't suggest Mitra/morning-briefing reframing (deviates from problem statement)
- ❌ Don't build Vertex AI Forecasting (on hold)
- ❌ Don't propose predictive policing in Minority Report framing
- ❌ Don't ask "should I proceed?" — auto mode is on
- ❌ Don't write huge analyses when a 3-line answer works
- ❌ Don't ignore parallelism — always use background agents for independent work

## Voice strategy (locked)

| Language | Path |
|---|---|
| **Kannada** | Gemini Live API (`gemini-live-3-5-translate` or equivalent — native multimodal, single bidirectional call) |
| **English/Hindi** | Catalyst Zia STT + TTS |
| **Fallback (any language)** | Google Cloud STT/TTS (`kn-IN-Wavenet-A` for Kannada TTS) |

## LLM strategy (locked)

| Task | Model | Why |
|---|---|---|
| Intent router | Qwen 2.5 7B (Catalyst QuickML) | Fast, cheap, Catalyst-native |
| SQL/Cypher generation | Qwen 2.5 14B Instruct (Catalyst QuickML) | Catalyst primary |
| Synthesizer (Kannada premium) | Gemini 2.5 Pro | Documented quality gap — A/B tested |
| Synthesizer (English routine) | Qwen 2.5 14B Instruct | Catalyst primary |
| Embeddings (RAG) | `gemini-embedding-001` if QuickML RAG weak | Multilingual quality |

## Team (5 people)

| Owner | Module | Files |
|---|---|---|
| Person A | Data engineer | `data/`, `app/data-pipeline/`, Data Store schema |
| Person B | AI orchestrator | `app/backend/functions/`, `app/backend/circuits/` |
| Person C | Graph + predictive | `app/data-pipeline/neo4j_ingest.py`, Zia AutoML |
| Person D | Frontend + maps | `app/frontend/` |
| Person E | Voice + demo | Voice integration, `app/validation/`, demo script |

---

## Key dates

| Date | Event |
|---|---|
| **TODAY** | Implementation in progress |
| 19 Jul 2026 | Registration closes |
| 26 Jul 2026 | **Prototype submission deadline** |
| 19 Aug 2026 | Initial shortlist announced |
| 9 Sep 2026 | Final shortlist announced |
| **26 Sep 2026** | **Grand Finale (in-person demo day)** |

---

*Last updated: 2026-06-16. If you change a locked decision, append to `design.md` Section 18 Decision Log.*
