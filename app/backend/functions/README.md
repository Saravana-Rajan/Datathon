# Catalyst Functions

This directory holds every Catalyst Function in the KSP Saathi backend.
Each function is a self-contained Python package with its own
`catalyst-config.json` and `requirements.txt`, but they all import the
project-wide helpers from `../shared/`.

## Planned functions

| Function | Type | Purpose |
|---|---|---|
| `hello/` | I/O | Catalyst init smoke test (returns "ok" + project id) |
| `intent-router/` | I/O | Classifies the user query into one of the 7 intents (see `shared/types.py::Intent`). Uses Qwen 2.5 7B on Catalyst QuickML. |
| `sql-generator/` | I/O | Translates natural-language → ANSI SQL against the Catalyst Data Store. |
| `cypher-generator/` | I/O | Translates → Cypher against Neo4j AuraDB. |
| `rag-retriever/` | I/O | Embeds the query + top-k search over Catalyst QuickML RAG (Gemini embedding fallback). |
| `synthesizer/` | I/O | Combines tool results into the final answer (Qwen 2.5 14B or Gemini 2.5 Pro). |
| `audit-logger/` | Event | Subscribes to Catalyst Signals from every function, fan-in writer to NoSQL `audit_log`. |
| `pdf-exporter/` | I/O | Uses Catalyst SmartBrowz to render the conversation transcript to a branded PDF and store in Stratus. |

The orchestrator (`../circuits/main-query-flow.yaml`) wires these
functions together — see design.md §6.1.

## How to add a new function

1. Scaffold the directory:
   ```
   functions/<name>/
   ├── catalyst-config.json   # Catalyst-required manifest
   ├── requirements.txt       # function-specific deps; usually subset of /requirements.txt
   ├── main.py                # entrypoint with `handler(req, context)`
   └── __init__.py
   ```

2. Reference the shared helpers (Catalyst Functions can include sibling
   directories via the `include` field in `catalyst-config.json`):
   ```python
   from shared.catalyst_client import get_datastore, log_audit
   from shared.gemini_client import get_text_client
   from shared.types import RouterDecision, ToolResult
   from shared.prompts import router_prompt
   ```

3. Add the function to `../catalyst.json` if it needs explicit gateway
   routing (most functions are reachable through Catalyst API Gateway by
   default once deployed).

4. Local-test with the Catalyst CLI:
   ```
   catalyst serve --function <name>
   ```

5. Deploy:
   ```
   catalyst deploy --function <name>
   ```

## Handler conventions

Every function returns a `dict` matching one of the Pydantic models in
`shared/types.py`. Always wrap tool work in a try/except that emits a
`ToolResult(success=False, error=...)` instead of raising — the
synthesizer is built to degrade gracefully on tool failures.

```python
import time
from shared.types import ToolResult

def handler(request, context):
    started = time.monotonic()
    try:
        # ... do the work ...
        data = run_tool(request)
        return ToolResult(
            tool_name="sql_generator",
            success=True,
            data=data,
            latency_ms=int((time.monotonic() - started) * 1000),
        ).model_dump()
    except Exception as exc:
        return ToolResult(
            tool_name="sql_generator",
            success=False,
            error=str(exc),
            latency_ms=int((time.monotonic() - started) * 1000),
        ).model_dump()
```

## Audit trail (mandatory)

Every chat-turn-handling function must call
`shared.catalyst_client.log_audit(...)` exactly once before returning
its response to the orchestrator. Skipping the audit log fails the
explainability requirement (design.md §5.8, §11.3).
