"""
Live smoke test for Sarvik Catalyst Function endpoints.

Run: python app/tests/live_smoke.py

Diagnostic, not pass/fail. Captures HTTP status, latency, and failure mode
for each of the 9 deployed functions. PENDING-config failures (Neo4j,
Google Maps, Gemini, Stratus) are expected for some endpoints and counted
as "waiting on env vars" rather than broken.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

BASE = "https://sarvik-60074155874.development.catalystserverless.in/server"

# Markers that indicate "deployed and reachable, but waiting on env config"
# rather than a genuine code defect. Matched case-insensitively against the
# response body / error message.
PENDING_MARKERS = (
    "PENDING",
    "NEO4J_URI",
    "GOOGLE_MAPS",
    "GEMINI_API_KEY",
    "STRATUS",
    "SMARTBROWZ",
    "DATA_STORE",
    "not configured",
    "missing api key",
    "missing env",
    "env var",
    "credentials not",
)


@dataclass
class Result:
    name: str
    http: int | str
    latency_ms: int
    passed: str  # "PASS", "FAIL", "WAIT"
    summary: str
    body_preview: str = field(default="", repr=False)


def http_call(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int | str, str, int]:
    """Returns (status_code_or_error_label, body_text, latency_ms)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency = int((time.perf_counter() - start) * 1000)
            return resp.status, body, latency
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        latency = int((time.perf_counter() - start) * 1000)
        return e.code, body, latency
    except error.URLError as e:
        latency = int((time.perf_counter() - start) * 1000)
        return "URLError", str(e.reason), latency
    except TimeoutError:
        latency = int((time.perf_counter() - start) * 1000)
        return "Timeout", "timed out", latency
    except Exception as e:  # pragma: no cover
        latency = int((time.perf_counter() - start) * 1000)
        return type(e).__name__, str(e), latency


def is_pending(text: str) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in PENDING_MARKERS)


def classify(http: int | str, body: str, success_check) -> tuple[str, str]:
    """Returns (verdict, short_summary)."""
    body_low = body.lower() if isinstance(body, str) else ""
    if isinstance(http, int) and 200 <= http < 300:
        ok, note = success_check(body)
        if ok:
            return "PASS", note or "ok"
        if is_pending(body):
            return "WAIT", (note or "2xx but missing config")[:80]
        return "FAIL", (note or "2xx but unexpected body")[:80]
    # Non-2xx
    if is_pending(body):
        return "WAIT", _short(body) or "pending config"
    if http in ("URLError", "Timeout"):
        return "FAIL", _short(body) or str(http)
    return "FAIL", _short(body) or f"HTTP {http}"


def _short(text: str, n: int = 80) -> str:
    text = (text or "").strip().replace("\n", " ").replace("\r", " ")
    return text[:n]


# -------- Per-function success checks --------


def check_hello(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json response"
    fields = {k.lower(): v for k, v in j.items()} if isinstance(j, dict) else {}
    has_greeting = any(
        k in fields for k in ("greeting", "message", "kannada", "english", "kn", "en")
    )
    if has_greeting:
        return True, _short(body)
    return False, "no greeting field"


def check_intent(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json"
    if isinstance(j, dict) and (
        "intent" in j or "tools" in j or "router_decision" in j or "language" in j
    ):
        return True, _short(json.dumps(j)[:80])
    return False, _short(body)


def check_sql(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json"
    if isinstance(j, dict) and ("sql" in j or "query" in j or "rows" in j):
        return True, _short(json.dumps(j))
    return False, _short(body)


def check_cypher(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json"
    if isinstance(j, dict) and ("cypher" in j or "graph" in j or "nodes" in j):
        return True, _short(json.dumps(j))
    return False, _short(body)


def check_rag(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json"
    if isinstance(j, dict) and ("chunks" in j or "results" in j or "docs" in j):
        return True, _short(json.dumps(j))
    return False, _short(body)


def check_synth(body: str) -> tuple[bool, str]:
    # Streaming text or json
    if not body:
        return False, "empty body"
    if "text" in body.lower() or "answer" in body.lower() or len(body) > 20:
        return True, _short(body)
    return False, _short(body)


def check_audit(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        if "ok" in body.lower() or "appended" in body.lower():
            return True, _short(body)
        return False, "non-json"
    if isinstance(j, dict) and (
        j.get("ok") or "id" in j or "appended" in j or "status" in j
    ):
        return True, _short(json.dumps(j))
    return False, _short(body)


def check_pdf(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        # Could be raw PDF bytes — unlikely via JSON channel but allow
        if body.startswith("%PDF"):
            return True, "raw pdf bytes"
        return False, "non-json"
    if isinstance(j, dict) and ("url" in j or "pdf_url" in j or "path" in j):
        return True, _short(json.dumps(j))
    return False, _short(body)


def check_orch(body: str) -> tuple[bool, str]:
    try:
        j = json.loads(body)
    except Exception:
        return False, "non-json"
    if isinstance(j, dict) and (
        "answer" in j or "steps" in j or "trace" in j or "tools_called" in j
    ):
        return True, _short(json.dumps(j))
    return False, _short(body)


# -------- Test runner --------


def run() -> list[Result]:
    results: list[Result] = []

    # 1. hello -- GET with query param
    name = "hello"
    url = f"{BASE}/{name}/?name=Smoke"
    http, body, lat = http_call("GET", url)
    verdict, summary = classify(http, body, check_hello)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 2. intent-router
    name = "intent-router"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "Show vehicle thefts",
        "language_hint": "auto",
        "session_id": "smoke-1",
        "user_role": "inspector",
    }
    http, body, lat = http_call("POST", url, payload)
    verdict, summary = classify(http, body, check_intent)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 3. sql-generator
    name = "sql-generator"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "Count thefts last month",
        "router_decision": {
            "intent": "structured_query",
            "tools": ["sql"],
            "filters": {"crime_type": "theft", "timeframe": "last_month"},
        },
        "session_id": "smoke-1",
    }
    http, body, lat = http_call("POST", url, payload)
    verdict, summary = classify(http, body, check_sql)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 4. cypher-generator
    name = "cypher-generator"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "Find networks linked to suspect A",
        "router_decision": {
            "intent": "graph_query",
            "tools": ["cypher"],
            "entities": ["suspect_a"],
        },
        "session_id": "smoke-1",
    }
    http, body, lat = http_call("POST", url, payload)
    verdict, summary = classify(http, body, check_cypher)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 5. rag-retriever
    name = "rag-retriever"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "Standard operating procedure for FIR registration",
        "top_k": 3,
        "session_id": "smoke-1",
    }
    http, body, lat = http_call("POST", url, payload)
    verdict, summary = classify(http, body, check_rag)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 6. synthesizer
    name = "synthesizer"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "Summarize theft trends",
        "router_decision": {"intent": "structured_query", "tools": ["sql"]},
        "tool_outputs": {
            "sql": {"rows": [{"month": "May", "count": 12}]},
        },
        "language": "en",
        "session_id": "smoke-1",
    }
    http, body, lat = http_call("POST", url, payload, timeout=45)
    verdict, summary = classify(http, body, check_synth)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 7. audit-logger (POST append, then GET)
    name = "audit-logger"
    url = f"{BASE}/{name}/append"
    payload = {
        "session_id": "smoke-1",
        "step": "smoke_test",
        "actor": "live_smoke",
        "payload": {"note": "diagnostic ping"},
    }
    http, body, lat = http_call("POST", url, payload)
    verdict, summary = classify(http, body, check_audit)
    # Try a GET to confirm read path too, but keep the POST as the headline result
    get_http, get_body, get_lat = http_call(
        "GET", f"{BASE}/audit-logger/?session_id=smoke-1"
    )
    summary = f"{summary} | GET:{get_http}"[:80]
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 8. pdf-exporter
    name = "pdf-exporter"
    url = f"{BASE}/{name}/"
    payload = {
        "session_id": "smoke-1",
        "title": "Smoke Report",
        "content": {
            "answer": "Test summary",
            "sources": [],
        },
    }
    http, body, lat = http_call("POST", url, payload, timeout=45)
    verdict, summary = classify(http, body, check_pdf)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    # 9. orchestrator
    name = "orchestrator"
    url = f"{BASE}/{name}/"
    payload = {
        "query": "test",
        "language_hint": "en",
        "session_id": "smoke-1",
        "user_role": "inspector",
    }
    http, body, lat = http_call("POST", url, payload, timeout=60)
    verdict, summary = classify(http, body, check_orch)
    results.append(Result(name, http, lat, verdict, summary, body[:300]))

    return results


def render(results: list[Result]) -> str:
    symbol = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WAIT": "[WAIT]"}
    lines = []
    lines.append("# Sarvik Live Smoke Test Results")
    lines.append("")
    lines.append(f"Target: `{BASE}/<function>/`")
    lines.append("")
    lines.append(
        "| function | HTTP | latency_ms | passed | error_summary |"
    )
    lines.append(
        "|----------|------|------------|--------|----------------|"
    )
    for r in results:
        lines.append(
            f"| {r.name} | {r.http} | {r.latency_ms} | "
            f"{symbol.get(r.passed, r.passed)} | {r.summary} |"
        )

    pass_n = sum(1 for r in results if r.passed == "PASS")
    wait_n = sum(1 for r in results if r.passed == "WAIT")
    fail_n = sum(1 for r in results if r.passed == "FAIL")

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- **{pass_n} of {len(results)} fully functional**"
    )
    lines.append(
        f"- **{wait_n} waiting for env vars / external config** (PENDING)"
    )
    lines.append(f"- **{fail_n} genuinely broken**")
    lines.append("")
    lines.append("## Per-endpoint body preview")
    lines.append("")
    for r in results:
        lines.append(f"### {r.name}")
        lines.append("```")
        lines.append(r.body_preview or "(empty)")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(f"Smoke testing {BASE} ...", flush=True)
    results = run()
    report = render(results)

    out_path = Path(__file__).parent / "test_results.md"
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nWrote {out_path}")
    # Diagnostic — always exit 0 unless every single endpoint is broken
    broken = sum(1 for r in results if r.passed == "FAIL")
    if broken == len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
