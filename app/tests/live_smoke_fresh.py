"""
Fresh smoke test for Sarvik Catalyst Function endpoints.
Uses exact payloads specified by user request.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

BASE = "https://sarvik-60074155874.development.catalystserverless.in/server"


def http_call(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int | str, str, int, str]:
    """Returns (status_code_or_error_label, body_text, latency_ms, content_type)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency = int((time.perf_counter() - start) * 1000)
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, body, latency, ctype
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        latency = int((time.perf_counter() - start) * 1000)
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
        return e.code, body, latency, ctype
    except error.URLError as e:
        latency = int((time.perf_counter() - start) * 1000)
        return "URLError", str(e.reason), latency, ""
    except TimeoutError:
        latency = int((time.perf_counter() - start) * 1000)
        return "Timeout", "timed out", latency, ""
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return type(e).__name__, str(e), latency, ""


def classify_body(body: str, ctype: str) -> str:
    """Return 'JSON', 'SSE', 'TEXT', or 'EMPTY'."""
    if not body:
        return "EMPTY"
    if "event-stream" in ctype.lower() or body.lstrip().startswith("data:") or body.lstrip().startswith("event:"):
        return "SSE"
    try:
        json.loads(body)
        return "JSON"
    except Exception:
        return "TEXT"


def run():
    tests = [
        ("hello", "GET", f"{BASE}/hello/?name=Test", None, 30),
        ("intent-router", "POST", f"{BASE}/intent-router/", {
            "query": "Show vehicle thefts",
            "language_hint": "auto",
            "session_id": "smoke",
            "user_role": "sub_inspector",
        }, 30),
        ("sql-generator", "POST", f"{BASE}/sql-generator/", {
            "request_id": "smoke",
            "query": "thefts last month",
            "language": "en",
            "router_decision": {"entities": {"crime_type": "vehicle_theft"}},
        }, 30),
        ("cypher-generator", "POST", f"{BASE}/cypher-generator/", {
            "request_id": "smoke",
            "query": "network around Ravi Kumar",
            "language": "en",
            "router_decision": {"entities": {"person": "Ravi Kumar"}},
        }, 30),
        ("rag-retriever", "POST", f"{BASE}/rag-retriever/", {
            "request_id": "smoke",
            "query": "theft patterns",
            "language": "en",
            "top_k": 3,
        }, 30),
        ("synthesizer", "POST", f"{BASE}/synthesizer/", {
            "request_id": "smoke",
            "query": "test",
            "language": "en",
            "router_decision": {},
            "tool_results": [],
        }, 45),
        ("audit-logger", "POST", f"{BASE}/audit-logger/append", {
            "request_id": "smoke-1",
            "step_type": "input",
            "step_data": {"q": "test"},
        }, 30),
        ("pdf-exporter", "POST", f"{BASE}/pdf-exporter/", {
            "session_id": "smoke-1",
            "include_audit": True,
            "language": "en",
        }, 45),
        ("orchestrator", "POST", f"{BASE}/orchestrator/", {
            "query": "test",
            "language_hint": "en",
            "session_id": "smoke",
            "user_role": "sub_inspector",
        }, 60),
    ]

    results = []
    for name, method, url, payload, timeout in tests:
        print(f"  -> {name} ...", flush=True)
        http, body, lat, ctype = http_call(method, url, payload, timeout=timeout)
        body_type = classify_body(body, ctype)
        preview = (body or "").replace("\n", " ").replace("\r", " ").strip()[:150]
        results.append({
            "name": name,
            "http": http,
            "latency_ms": lat,
            "body_type": body_type,
            "preview": preview,
            "ctype": ctype,
            "full_body": body[:500],
        })
    return results


def render(results) -> str:
    lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("# Sarvik Live Smoke Test Results (Fresh Run)")
    lines.append("")
    lines.append(f"Run at: {ts}")
    lines.append(f"Target: `{BASE}/<function>/`")
    lines.append("")
    lines.append("| # | function | HTTP | latency (ms) | body type | response preview (first 150 chars) |")
    lines.append("|---|----------|------|--------------|-----------|--------------------------------------|")
    for i, r in enumerate(results, 1):
        prev = r["preview"].replace("|", "\\|")
        lines.append(f"| {i} | {r['name']} | {r['http']} | {r['latency_ms']} | {r['body_type']} | `{prev}` |")
    lines.append("")
    lines.append("## Per-function one-line summary")
    lines.append("")
    for r in results:
        verdict = "OK" if (isinstance(r["http"], int) and 200 <= r["http"] < 300) else "ISSUE"
        lines.append(f"- **{r['name']}** [{verdict}] HTTP {r['http']} in {r['latency_ms']} ms, "
                     f"body={r['body_type']}, ctype=`{r['ctype']}` -- `{r['preview'][:100]}`")
    lines.append("")
    lines.append("## Full body excerpts (first 500 chars)")
    lines.append("")
    for r in results:
        lines.append(f"### {r['name']}")
        lines.append("```")
        lines.append(r["full_body"] or "(empty)")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(f"Smoke testing {BASE} ...", flush=True)
    results = run()
    report = render(results)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(__file__).parent / f"live_smoke_results_{ts}.md"
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
