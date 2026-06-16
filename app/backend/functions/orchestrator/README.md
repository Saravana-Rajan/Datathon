# orchestrator — Sarvik BRAIN (replaces Catalyst Circuits)

> Codename: `ksp-saathi` · Owner: Person B · Type: Catalyst Advanced I/O Function

## Why this exists

Catalyst **Circuits is not available in the Catalyst India DC** (verified
2026-06-16 — see `design.md` §18 Decision Log). The YAML at
`app/backend/circuits/main-query-flow.yaml` is still the **authoritative
spec**, but the orchestration itself runs here, in Python, with proper
async/await fan-out.

This Function is the brain of Sarvik: it routes every investigator
query, fans out specialist tools in parallel, streams the synthesizer's
answer back to the client over Server-Sent Events, and writes the
complete audit trail to NoSQL.

## Architecture

```
       ┌────────────────────────────────────────────────────────┐
       │  Client (Next.js front-end on Catalyst Web Hosting)    │
       │  POST /server/orchestrator     (SSE-consuming fetch)   │
       └─────────────────────────┬──────────────────────────────┘
                                 │
       ┌─────────────────────────▼──────────────────────────────┐
       │  orchestrator   (this Function — Advanced I/O)         │
       │                                                        │
       │  Step 1 — emit `started`         (request_id UUIDv4)   │
       │  Step 2 — intent-router  ── unary ───────────────►     │
       │            (POST /server/intent-router, 5s timeout)    │
       │  Step 3 — fan-out via asyncio.gather():                │
       │            ├── sql-generator                           │
       │            ├── cypher-generator         (8s each,      │
       │            ├── rag-retriever             retry x1)     │
       │            └── predictive-service                      │
       │           Per tool: emit tool_started → tool_done      │
       │  Step 4 — stream_function("synthesizer", …) ─────►     │
       │            proxy SSE events 1:1 to the client          │
       │  Step 5 — invoke_fire_and_forget("audit-logger", …)    │
       │           (never blocks the user)                      │
       └────────────────────────────────────────────────────────┘
```

## SSE event reference

Events emitted **by this orchestrator**:

| Type | Payload | When |
|---|---|---|
| `started` | `request_id` | Right after validation |
| `routed` | `intent`, `language`, `confidence`, `ms` | Router returned |
| `tool_started` | `tool` | A specialist call dispatched |
| `tool_done` | `tool`, `ok`, `ms`, `error?` | Specialist completed (or failed) |
| `error` | `stage`, `message` | Router / tool / synth failure |
| `orchestrator_done` | `total_ms`, `router_ms`, `synth_ms`, `tool_count`, `warning_count` | Always last |

Events **proxied from the synthesizer** (verbatim):

`text_chunk` · `viz_spec` · `audit_chain` · `done`

## HTTP contract

**POST** `/server/orchestrator`

```json
{
  "query": "show all chain snatchings near Indiranagar last 30 days",
  "language_hint": "auto",
  "session_id": "sess-abc-123",
  "user_role": "inspector"
}
```

Response: `Content-Type: text/event-stream`. The client uses the Vercel
AI SDK `useChat` hook (or a raw `EventSource`) to consume events.

## Environment variables

| Name | Default | Purpose |
|---|---|---|
| `CATALYST_API_BASE` | `https://ksp-saathi-60067540097.catalystserverless.in/server` | Base URL for sibling functions when per-function URL is unset |
| `CATALYST_TOKEN` | *(required)* | Bearer token sent on every internal call |
| `FN_INTENT_ROUTER_URL` | *(optional)* | Explicit URL override for the router |
| `FN_SQL_GENERATOR_URL` | *(optional)* | …same pattern for every downstream function |
| `FN_CYPHER_GENERATOR_URL` | *(optional)* | |
| `FN_RAG_RETRIEVER_URL` | *(optional)* | |
| `FN_PREDICTIVE_SERVICE_URL` | *(optional)* | Stub OK — synth degrades gracefully |
| `FN_SYNTHESIZER_URL` | *(optional)* | |
| `FN_AUDIT_LOGGER_URL` | *(optional)* | |
| `ORCH_TOTAL_TIMEOUT_S` | `30` | Hard wall-clock ceiling |
| `ORCH_TOOL_TIMEOUT_S` | `8` | Per-tool soft timeout |
| `ORCH_ROUTER_TIMEOUT_S` | `5` | Intent-router only |
| `ORCH_SYNTH_TIMEOUT_S` | `20` | Synthesizer SSE stream |
| `ORCH_AUDIT_TIMEOUT_S` | `3` | Audit fire-and-forget |
| `ORCH_RETRY_ATTEMPTS` | `2` | Total attempts on transient HTTP errors |
| `ORCH_RETRY_BACKOFF_MS` | `250` | Linear backoff between retries |
| `LOG_LEVEL` | `INFO` | Standard Python logging level |

URL resolution order for any function `<name>`:

1. `FN_<UPPER_NAME>_URL` env var (hyphens → underscores).
2. `CATALYST_API_BASE` + `/<name>`.

## How to add a new tool

1. **Update `tools_for_intent`** in `index.py` — map the new intent (or
   add the tool to an existing intent's branch list).

2. **Update `_tool_payload`** if the tool needs anything beyond the
   standard envelope (`request_id`, `session_id`, `user_role`,
   `normalized_query`, `entities`, `language`).

3. **Provision a URL**: either set `FN_<TOOL>_URL` directly or rely on
   `CATALYST_API_BASE + /<tool-name>`.

4. **Set the per-tool soft timeout** if 8s is wrong for it. The cleanest
   way is to push the override down into `invoke_function(timeout=…)`
   inside `_run_one_tool` — keep it consistent with the spec's
   `timeout_ms` for the matching branch in `main-query-flow.yaml`.

5. **Add a fixture row to `test_orchestrator.py`** — at minimum extend
   the `test_tools_for_intent` parametrize list. If the tool needs
   different response shape, add a dedicated test.

6. **Mirror the change in `circuits/main-query-flow.yaml`** so the spec
   stays in sync with reality (the YAML is also our deploy plan if
   Catalyst Circuits ever lands in the India DC).

## Failure semantics

| Failure | What happens |
|---|---|
| Router timeout / 5xx | Falls back to `intent=lookup, confidence=0.0`, emits an `error` event, and continues |
| One tool fails | `tool_done` with `ok=false`, synth runs with partial results + warnings |
| All tools fail | Synth runs with just the router decision (still produces a clarifier answer) |
| Synth fails | `error{stage:synth}`, no answer text, audit still fires |
| Audit fails | Logged at WARNING, the user is unaffected |
| Total > 30s | `error{stage:orchestrator, message:total_timeout_30.0s}`, then `orchestrator_done` |

Audit failures **never** fail the user query — Catalyst Signals + a
reconciliation cron job will pick up missed entries from this Function's
INFO logs.

## Local dev

```bash
cd app/backend/functions/orchestrator
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest test_orchestrator.py -v
```

The test suite is hermetic (monkeypatched `invoke_function` / `stream_function`)
— no Catalyst credentials or sibling Functions required.

## Spec source-of-truth

`app/backend/circuits/main-query-flow.yaml` — this Python implementation
mirrors every step, timeout, and failure mode of that YAML. If you change
one, change the other.
