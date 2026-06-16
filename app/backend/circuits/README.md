# `app/backend/circuits/` — KSP Saathi Orchestration

Quick guide for Person B (AI orchestrator). Read this before editing any flow.

---

## What lives here

| File | Purpose | Trigger |
|---|---|---|
| `main-query-flow.yaml` | The primary conversational query path. Route intent → fan out specialists → stream synthesizer answer → audit. | HTTP (every chat turn from the frontend) |
| `embedding-batch-flow.yaml` | Backfill embeddings for newly-ingested FIRs. | Catalyst Cron, every 6 hours |
| `audit-export-flow.yaml` | "Export PDF" button → fetch audit → SmartBrowz → Stratus → Mail. | HTTP (user click) |

---

## IMPORTANT — Catalyst Circuits + India DC

Catalyst Circuits is **NOT available in the India DC** (see `docs/catalyst-reference.md` §8).

KSP Saathi must run in the India DC (IT Act 2008 compliance, `design.md` §2). So these YAML files are the **authoritative orchestration specification** consumed two ways:

1. **In-Python orchestrator (production path).** `functions/orchestrator/` mirrors `main-query-flow.yaml` using sequential + `concurrent.futures.ThreadPoolExecutor` fan-out, calling sibling functions with `app.function('x').execute(...)`. The YAML is the contract; the Python implementation must stay in sync.
2. **Catalyst Circuits (future path).** If we ever deploy a non-India tenant (US/JP/SA DC support Circuits), the YAML can be imported directly. Schema follows the documented Basic I/O constraints (HTTP GET/POST functions, JSON in/out, no Cron/Event/Advanced I/O participants).

**Rule of thumb:** edit the YAML first, then mirror the change in `functions/orchestrator/main.py`.

---

## Running locally vs deployed

### Locally (dev loop)

```bash
# From app/backend/
catalyst serve                              # boots all functions on localhost
# In another shell, hit the orchestrator entrypoint:
curl -X POST http://localhost:3000/server/orchestrator \
  -H 'Content-Type: application/json' \
  -d '{
    "request_id": "test-001",
    "query": "Show chain snatchings near Indiranagar last 30 days",
    "language_hint": "en",
    "session_id": "sess-test",
    "user_role": "inspector"
  }'
```

For the cron flow:
```bash
# Force-trigger the embed-new-firs function directly
curl -X POST http://localhost:3000/server/embed-new-firs \
  -H 'Content-Type: application/json' \
  -d '{"batch_size": 100, "dry_run": true}'
```

For the audit export flow:
```bash
curl -X POST http://localhost:3000/server/audit-export \
  -H 'Content-Type: application/json' \
  -d '{
    "request_id": "exp-001",
    "session_id": "sess-test",
    "user_id": "u-123",
    "user_role": "inspector",
    "user_email": "officer@ksp.gov.in"
  }'
```

### Deployed (Catalyst)

```bash
catalyst deploy --only functions            # push functions
# Cron schedule for embedding-batch-flow is configured via:
catalyst cron:create embed-new-firs --schedule "0 */6 * * *" --timezone Asia/Kolkata
```

---

## How variables flow between steps

Each step gets an `id`. Downstream steps reference any prior step's output using the templating syntax:

```yaml
{{ step-id.output_field }}
{{ step-id.output.nested.field }}
```

You can also reference:
- `{{ input.foo }}` — top-level flow input
- `{{ runtime.elapsed_ms }}` — runtime metadata (elapsed time, started_at, trace_id, …)
- `{{ step-id.output.field | default(null) }}` — Jinja-style fallback
- `{{ 'tabular' in route.output.intents }}` — conditional expressions on `when:`

### Worked example (from `main-query-flow.yaml`)

```yaml
- id: route
  function: intent-router
  output_schema: { intents: array, normalized_query: string }

- id: tabular
  when: "{{ 'tabular' in route.output.intents }}"
  function: sql-generator
  input:
    normalized_query: "{{ route.output.normalized_query }}"   # ← reads step `route`
```

The synthesizer step then bundles every branch's output with `default(null)` so it can run on partials:

```yaml
tool_results:
  tabular:    "{{ specialists.branches.tabular.output    | default(null) }}"
  graph:      "{{ specialists.branches.graph.output      | default(null) }}"
```

---

## Error handling model

| Knob | Where | Default | Effect |
|---|---|---|---|
| `execution.total_timeout_ms` | flow root | 30000 (main), 60000 (export), 900000 (batch) | Hard ceiling. After this, flow aborts. |
| `execution.default_retry` | flow root | 2 attempts, 250 ms backoff | Inherited by every step unless overridden. |
| `step.retry` | per step | — | Overrides the default for that step. |
| `step.timeout_ms` | per step | 5000 | Per-call deadline. |
| `step.on_error` | per step | `fail_flow` | `continue_with_warnings` / `log_only` / `respond_with_failure`. |
| `parallel.fail_strategy` | parallel block | `collect_partial` | `collect_partial` = sibling branches keep running; failed ones surface in `specialists.errors`. |
| `synthesize.on_partial_inputs: proceed` | synthesizer | — | Critical: synthesizer always runs even if some branches failed. |

### Failure flow for `main-query-flow.yaml`

1. A specialist (e.g. `graph`) times out → marked failed in `specialists.errors`.
2. Sibling branches finish normally.
3. `synthesize` runs with whatever results landed + `warnings: [{branch: graph, reason: TIMEOUT}]`.
4. The synthesizer prompt is engineered to acknowledge missing branches ("I couldn't reach the network graph this time, but here's what the case records show…").
5. `audit` records every branch result (success or failure) so the "Why?" drawer is honest.

---

## Debugging tips

1. **Find the request_id first.** Every step echoes `request_id` into its logs. In Catalyst console → Logs, filter by `request_id=...` to see the whole chain.
2. **Use `dry_run: true` on `embedding-batch-flow`** before letting it loose on 50K records — it returns the count of FIRs it *would* embed.
3. **Synthesizer stream not arriving?** Check that `synthesize.streaming: true` is honored by the in-Python orchestrator (it should `yield` chunks, not `return`).
4. **Branch silently skipped?** The `when:` expression evaluated falsy. Log `route.output.intents` and verify the router emitted the expected label (one of `tabular | graph | semantic | lookup | predictive | geo | meta`).
5. **`{{ … | default(null) }}` is your friend.** Synthesizer + audit must NEVER crash because a branch returned nothing.
6. **NoSQL audit doc missing?** `audit.on_error: log_only` swallows errors by design — check function logs for `audit-logger` directly, don't rely on the flow's top-level status.
7. **Catalyst SmartBrowz Kannada glyphs broken?** This is design.md §17 open Q6. Confirm `font_family: "Noto Sans Kannada"` is installed in the SmartBrowz environment; otherwise embed the TTF in the HTML template as base64.

---

## How to add a new step

1. **Pick a function.** Either reuse an existing function in `app/backend/functions/` or scaffold a new Basic I/O function:
   ```bash
   catalyst functions:add --name my-new-step --type basic
   ```
2. **Declare the step in YAML.** Add a block under `steps:` (or inside an existing `parallel.branches:`):
   ```yaml
   - id: my_new_step
     name: Human-readable description
     function: my-new-step
     type: http_invoke
     method: POST
     depends_on: [route]              # explicit dependency
     when: "{{ 'my_intent' in route.output.intents }}"   # optional
     timeout_ms: 4000
     input:
       request_id:       "{{ input.request_id }}"
       normalized_query: "{{ route.output.normalized_query }}"
     output_schema:
       type: object
       properties:
         result: { type: string }
   ```
3. **Update the in-Python orchestrator.** Add the matching call in `functions/orchestrator/main.py` so India DC behavior matches the spec.
4. **Plumb the output into the synthesizer.** Add the new branch under `synthesize.input.tool_results.*` with `| default(null)`.
5. **Plumb into the audit log.** Add to `audit.input.tool_calls.*`.
6. **Test.** Start with `dry_run`-style flags and minimal payloads, then run an end-to-end query.
7. **Update this README.** New step deserves a one-liner in the file table at the top.

---

## File-level conventions

- `apiVersion` is `catalyst.zoho.com/circuits/v1` — flag any schema drift with `# verify schema` and we'll reconcile at the 11 Jun Catalyst workshop.
- `metadata.owner` should always be `person-b` for circuits; change if ownership shifts.
- `version` follows semver. Bump minor on additive changes, major on breaking input/output shape changes.
- Comments above every step explain *why*, not *what* — Python mirrors the YAML, so keep both readable.

---

*Last updated: 2026-06-16. Maintainer: Person B (AI orchestrator).*
