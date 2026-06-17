# Sarvik Live Smoke Test Results

Target: `https://sarvik-60074155874.development.catalystserverless.in/server/<function>/`

| function | HTTP | latency_ms | passed | error_summary |
|----------|------|------------|--------|----------------|
| hello | 200 | 2261 | [PASS] | {"catalyst_sdk":{"error":"CatalystAppError: {'code': 'INVALID_APP_NAME', 'messag |
| intent-router | 500 | 1863 | [FAIL] | {"error": "ModuleNotFoundError(\"No module named 'shared'\")"} |
| sql-generator | 200 | 1772 | [PASS] | {"execution_ms": 0, "ok": false, "request_id": "", "results": [], "row_count": 0 |
| cypher-generator | 200 | 1901 | [PASS] | {"cypher": "", "execution_ms": 0, "ok": false, "request_id": "", "results": {"ed |
| rag-retriever | 200 | 2476 | [FAIL] | {"error":"RuntimeError: shared.gemini_client not importable. Ensure backend/shar |
| synthesizer | 500 | 1682 | [FAIL] | {"error": "AttributeError(\"'NoneType' object has no attribute '__dict__'\")"} |
| audit-logger | 500 | 1964 | [FAIL] | {"error": "TypeError(\"Unable to evaluate type annotation 'str | None'. If you a |
| pdf-exporter | 200 | 1821 | [FAIL] | {"error":"session not found: smoke-1","latency_ms":1,"ok":false,"service":"ksp-s |
| orchestrator | 500 | 2317 | [FAIL] | {"error": "TypeError(\"handler() missing 1 required positional argument: 'basic_ |

## Summary

- **3 of 9 fully functional**
- **0 waiting for env vars / external config** (PENDING)
- **6 genuinely broken**

## Per-endpoint body preview

### hello
```
{"catalyst_sdk":{"error":"CatalystAppError: {'code': 'INVALID_APP_NAME', 'message': 'App name must be a non-empty string', 'value': <Request 'http://sarvik-60074155874.development.catalystserverless.in:443/?name=Smoke' [GET]>}","nosql_reachable":false,"sdk_imported":true,"sdk_initialized":false},"en
```

### intent-router
```
{"error": "ModuleNotFoundError(\"No module named 'shared'\")"}
```

### sql-generator
```
{"execution_ms":0,"ok":false,"request_id":"","results":[],"row_count":0,"sql":"","warnings":["llm_call_failed:RuntimeError"]}

```

### cypher-generator
```
{"cypher":"","execution_ms":0,"ok":false,"request_id":"","results":{"edges":[],"nodes":[]},"warnings":["llm_call_failed:ValueError"]}

```

### rag-retriever
```
{"error":"RuntimeError: shared.gemini_client not importable. Ensure backend/shared/ is on sys.path or bundled in the function.","latency_ms":1,"ok":false,"service":"ksp-saathi-rag-retriever","timestamp_utc":"2026-06-17T08:37:25.582324Z","trace":"Traceback (most recent call last):\n  File \"/catalyst
```

### synthesizer
```
{"error": "AttributeError(\"'NoneType' object has no attribute '__dict__'\")"}
```

### audit-logger
```
{"error": "TypeError(\"Unable to evaluate type annotation 'str | None'. If you are making use of the new typing syntax (unions using `|` since Python 3.10 or builtins subscripting since Python 3.9), you should either replace the use of new syntax with the existing `typing` constructs or install the 
```

### pdf-exporter
```
{"error":"session not found: smoke-1","latency_ms":1,"ok":false,"service":"ksp-saathi-pdf-exporter","timestamp_utc":"2026-06-17T08:37:31.366776Z","version":"1.0.0"}

```

### orchestrator
```
{"error": "TypeError(\"handler() missing 1 required positional argument: 'basic_io'\")"}
```
