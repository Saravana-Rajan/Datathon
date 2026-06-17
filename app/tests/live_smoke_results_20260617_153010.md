# Sarvik Live Smoke Test Results (Fresh Run)

Run at: 2026-06-17 15:30:10
Target: `https://sarvik-60074155874.development.catalystserverless.in/server/<function>/`

| # | function | HTTP | latency (ms) | body type | response preview (first 150 chars) |
|---|----------|------|--------------|-----------|--------------------------------------|
| 1 | hello | 200 | 2310 | JSON | `{"catalyst_sdk":{"error":"CatalystAppError: {'code': 'INVALID_APP_NAME', 'message': 'App name must be a non-empty string', 'value': <Request 'http://s` |
| 2 | intent-router | 200 | 3103 | JSON | `{"body":"{\"confidence\":0.3,\"entities\":{},\"intent\":\"tabular_query\",\"language\":\"en\",\"reasoning\":\"Heuristic fallback: no strong signal, de` |
| 3 | sql-generator | 200 | 1822 | JSON | `{"execution_ms":0,"ok":false,"request_id":"smoke","results":[],"row_count":0,"sql":"","warnings":["llm_call_failed:RuntimeError"]}` |
| 4 | cypher-generator | 200 | 2199 | JSON | `{"cypher":"","execution_ms":0,"ok":false,"request_id":"smoke","results":{"edges":[],"nodes":[]},"warnings":["llm_call_failed:RuntimeError"]}` |
| 5 | rag-retriever | 200 | 5073 | JSON | `{"error":"TypeError: _TypedDictMeta.__new__() got an unexpected keyword argument 'extra_items'","latency_ms":912,"ok":false,"service":"ksp-saathi-rag-` |
| 6 | synthesizer | 500 | 5538 | JSON | `{"error": "AttributeError(\"'NoneType' object has no attribute '__dict__'\")"}` |
| 7 | audit-logger | 200 | 2455 | JSON | `{"detail":"shared.catalyst_client unavailable: No module named 'httpx'","error":"audit_store_unavailable","latency_ms":6,"ok":false,"region":"IN","ser` |
| 8 | pdf-exporter | 200 | 2842 | JSON | `{"error":"session not found: smoke-1","latency_ms":1118,"ok":false,"service":"ksp-saathi-pdf-exporter","timestamp_utc":"2026-06-17T10:00:09.295899Z","` |
| 9 | orchestrator | 500 | 2471 | TEXT | `<html>   <head>     <title>Internal Server Error</title>   </head>   <body>     <h1><p>Internal Server Error</p></h1>        </body> </html>` |

## Per-function one-line summary

- **hello** [OK] HTTP 200 in 2310 ms, body=JSON, ctype=`application/json` -- `{"catalyst_sdk":{"error":"CatalystAppError: {'code': 'INVALID_APP_NAME', 'message': 'App name must b`
- **intent-router** [OK] HTTP 200 in 3103 ms, body=JSON, ctype=`application/json` -- `{"body":"{\"confidence\":0.3,\"entities\":{},\"intent\":\"tabular_query\",\"language\":\"en\",\"reas`
- **sql-generator** [OK] HTTP 200 in 1822 ms, body=JSON, ctype=`application/json` -- `{"execution_ms":0,"ok":false,"request_id":"smoke","results":[],"row_count":0,"sql":"","warnings":["l`
- **cypher-generator** [OK] HTTP 200 in 2199 ms, body=JSON, ctype=`application/json` -- `{"cypher":"","execution_ms":0,"ok":false,"request_id":"smoke","results":{"edges":[],"nodes":[]},"war`
- **rag-retriever** [OK] HTTP 200 in 5073 ms, body=JSON, ctype=`application/json` -- `{"error":"TypeError: _TypedDictMeta.__new__() got an unexpected keyword argument 'extra_items'","lat`
- **synthesizer** [ISSUE] HTTP 500 in 5538 ms, body=JSON, ctype=`application/json` -- `{"error": "AttributeError(\"'NoneType' object has no attribute '__dict__'\")"}`
- **audit-logger** [OK] HTTP 200 in 2455 ms, body=JSON, ctype=`application/json` -- `{"detail":"shared.catalyst_client unavailable: No module named 'httpx'","error":"audit_store_unavail`
- **pdf-exporter** [OK] HTTP 200 in 2842 ms, body=JSON, ctype=`application/json` -- `{"error":"session not found: smoke-1","latency_ms":1118,"ok":false,"service":"ksp-saathi-pdf-exporte`
- **orchestrator** [ISSUE] HTTP 500 in 2471 ms, body=TEXT, ctype=`text/html` -- `<html>   <head>     <title>Internal Server Error</title>   </head>   <body>     <h1><p>Internal Serv`

## Full body excerpts (first 500 chars)

### hello
```
{"catalyst_sdk":{"error":"CatalystAppError: {'code': 'INVALID_APP_NAME', 'message': 'App name must be a non-empty string', 'value': <Request 'http://sarvik-60074155874.development.catalystserverless.in:443/?name=Test' [GET]>}","nosql_reachable":false,"sdk_imported":true,"sdk_initialized":false},"env_diagnostic":{"CATALYST_ENVIRONMENT":"unset","CATALYST_PROJECT_ID":"set","CATALYST_PROJECT_KEY":"unset","GEMINI_API_KEY":"set","GOOGLE_API_KEY":"unset","NEO4J_PASSWORD":"set","NEO4J_URI":"set","NEO4J_
```

### intent-router
```
{"body":"{\"confidence\":0.3,\"entities\":{},\"intent\":\"tabular_query\",\"language\":\"en\",\"reasoning\":\"Heuristic fallback: no strong signal, defaulting to tabular.\",\"request_id\":\"bd40d29d-6286-4eff-90d5-c14241aeb047\",\"router_latency_ms\":0}\n","headers":{"Content-Length":"223","Content-Type":"application/json"},"status":200}

```

### sql-generator
```
{"execution_ms":0,"ok":false,"request_id":"smoke","results":[],"row_count":0,"sql":"","warnings":["llm_call_failed:RuntimeError"]}

```

### cypher-generator
```
{"cypher":"","execution_ms":0,"ok":false,"request_id":"smoke","results":{"edges":[],"nodes":[]},"warnings":["llm_call_failed:RuntimeError"]}

```

### rag-retriever
```
{"error":"TypeError: _TypedDictMeta.__new__() got an unexpected keyword argument 'extra_items'","latency_ms":912,"ok":false,"service":"ksp-saathi-rag-retriever","timestamp_utc":"2026-06-17T09:59:58.455409Z","trace":"Traceback (most recent call last):\n  File \"/catalyst/index.py\", line 492, in handler\n    passages, method_used = retrieve(\n                            ^^^^^^^^^\n  File \"/catalyst/index.py\", line 455, in retrieve\n    passages = _gemini_fallback(query, top_k, filters, context)
```

### synthesizer
```
{"error": "AttributeError(\"'NoneType' object has no attribute '__dict__'\")"}
```

### audit-logger
```
{"detail":"shared.catalyst_client unavailable: No module named 'httpx'","error":"audit_store_unavailable","latency_ms":6,"ok":false,"region":"IN","service":"ksp-saathi-audit-logger","timestamp_utc":"2026-06-17T10:00:06.444161Z","version":"0.1.0"}

```

### pdf-exporter
```
{"error":"session not found: smoke-1","latency_ms":1118,"ok":false,"service":"ksp-saathi-pdf-exporter","timestamp_utc":"2026-06-17T10:00:09.295899Z","version":"1.0.0"}

```

### orchestrator
```
<html>
  <head>
    <title>Internal Server Error</title>
  </head>
  <body>
    <h1><p>Internal Server Error</p></h1>
    
  </body>
</html>

```
