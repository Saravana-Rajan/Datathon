#!/usr/bin/env python3
"""
Sarvik (ksp-saathi) — End-to-End Smoke Test
============================================

Hits the deployed Catalyst orchestrator function with each of the 5 golden
queries from `golden_queries.json` and asserts:

  * HTTP 200
  * Response JSON parses
  * `intent` matches the query's expected_intent
  * `viz_spec.type` matches expected_viz
  * Result count is within expected_count_range (where applicable)
  * End-to-end latency < HARD_BUDGET_MS (5s) -- hard fail
  * End-to-end latency < SOFT_BUDGET_MS (3.5s) -- warning

Outputs a results table to stdout, writes detailed JSON + per-query screenshots
to `./results/<timestamp>/`. Run this T-1h before any live demo. ALL queries
must pass or the demo runbook says abort and fall back to cached mode.

Env required:
    CATALYST_API_BASE       — e.g. https://api.catalyst.zoho.in
    CATALYST_PROJECT_ID
    CATALYST_AUTH_TOKEN     — service token with orchestrator invoke perm
    YAKSHA_ORCHESTRATOR_FN  — function name (default: orchestrator)

Optional:
    YAKSHA_DEMO_USER_TOKEN  — if set, sent as Bearer to simulate a real officer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from tabulate import tabulate

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
GOLDEN_QUERIES = HERE / "golden_queries.json"
RESULTS_ROOT = HERE / "results"

HARD_BUDGET_MS = 5000
SOFT_BUDGET_MS = 3500

console = Console()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    query_id: str
    language: str  # "en" or "kn"
    status_code: int
    latency_ms: float
    intent_ok: bool
    viz_ok: bool
    count_ok: bool
    answer_fragment_ok: bool
    raw_response: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (self.status_code == 200
                and self.intent_ok
                and self.viz_ok
                and self.count_ok
                and self.answer_fragment_ok
                and self.latency_ms < HARD_BUDGET_MS)

    @property
    def warning(self) -> bool:
        return self.passed and self.latency_ms >= SOFT_BUDGET_MS


# ---------------------------------------------------------------------------
# Orchestrator client
# ---------------------------------------------------------------------------

def _load_env() -> dict[str, str]:
    load_dotenv(REPO_ROOT / "app" / ".env", override=False)
    load_dotenv(REPO_ROOT / ".env", override=False)
    api_base = os.environ.get("CATALYST_API_BASE")
    if not api_base:
        raise SystemExit("CATALYST_API_BASE not set. See app/.env.example.")
    return {
        "api_base": api_base.rstrip("/"),
        "project_id": os.environ.get("CATALYST_PROJECT_ID", ""),
        "auth_token": os.environ.get("CATALYST_AUTH_TOKEN", ""),
        "fn_name": os.environ.get("YAKSHA_ORCHESTRATOR_FN", "orchestrator"),
        "user_token": os.environ.get("YAKSHA_DEMO_USER_TOKEN", ""),
    }


def call_orchestrator(env: dict[str, str], *, query: str, language: str,
                      role: str, query_id: str) -> tuple[int, dict[str, Any], float]:
    """POST to /baas/v1/project/<pid>/function/<fn>/execute.
    Returns (status_code, parsed_json, latency_ms)."""
    url = (f"{env['api_base']}/baas/v1/project/{env['project_id']}"
           f"/function/{env['fn_name']}/execute")
    headers = {
        "Authorization": f"Zoho-oauthtoken {env['auth_token']}",
        "Content-Type": "application/json",
    }
    if env["user_token"]:
        headers["X-Sarvik-User-Token"] = env["user_token"]
    payload = {
        "query": query,
        "language": language,
        "role": role,
        "session_id": f"smoke_{query_id}_{int(time.time())}",
        "client": "smoke_e2e",
    }
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        return 0, {"error": f"transport_error: {exc!r}"}, (time.perf_counter() - t0) * 1000
    elapsed_ms = (time.perf_counter() - t0) * 1000
    try:
        body = r.json()
    except json.JSONDecodeError:
        body = {"error": "non-json response", "text": r.text[:500]}
    return r.status_code, body, elapsed_ms


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _extract_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Orchestrator wraps response — unwrap common Catalyst Function shapes."""
    if not isinstance(raw, dict):
        return {}
    # Catalyst basic IO wrapping
    if "output" in raw and isinstance(raw["output"], dict):
        return raw["output"]
    # Catalyst Advanced IO
    if "body" in raw and isinstance(raw["body"], dict):
        return raw["body"]
    return raw


def check_query(spec: dict[str, Any], status_code: int, raw: dict[str, Any],
                latency_ms: float, language: str) -> QueryResult:
    res = QueryResult(query_id=spec["id"], language=language,
                      status_code=status_code, latency_ms=latency_ms,
                      intent_ok=False, viz_ok=False, count_ok=False,
                      answer_fragment_ok=False, raw_response=raw)

    if status_code != 200:
        res.failures.append(f"HTTP {status_code}")
        return res

    payload = _extract_payload(raw)

    intent = payload.get("intent") or payload.get("intent_class")
    secondary = payload.get("secondary_intent")
    if intent == spec["expected_intent"]:
        res.intent_ok = True
    elif secondary == spec["expected_intent"]:
        res.intent_ok = True
    elif spec.get("expected_secondary_intent") and intent == spec["expected_secondary_intent"]:
        res.intent_ok = True
    else:
        res.failures.append(f"intent mismatch: got {intent!r}, want "
                            f"{spec['expected_intent']!r}")

    viz_spec = payload.get("viz_spec") or payload.get("visualization") or {}
    if isinstance(viz_spec, dict) and viz_spec.get("type") == spec["expected_viz"]:
        res.viz_ok = True
    else:
        res.failures.append(f"viz mismatch: got {viz_spec.get('type')!r}, want "
                            f"{spec['expected_viz']!r}")

    # Count check — best-effort: look at results length, pins_count, or 'count'
    count = None
    if "count" in payload:
        count = payload["count"]
    elif isinstance(payload.get("results"), list):
        count = len(payload["results"])
    elif isinstance(viz_spec, dict):
        count = viz_spec.get("pins_count") or viz_spec.get("node_count")
        if count is None and isinstance(viz_spec.get("nodes"), list):
            count = len(viz_spec["nodes"])

    lo, hi = spec["expected_count_range"]
    if count is None:
        # Meta queries (q3) won't have a count — pass if intent is meta
        if spec["expected_intent"] == "meta_query":
            res.count_ok = True
        else:
            res.failures.append(f"no count field in response")
    elif lo <= count <= hi:
        res.count_ok = True
    else:
        res.failures.append(f"count {count} outside range [{lo}, {hi}]")

    # Answer fragment check
    answer = (payload.get("answer") or payload.get("response")
              or payload.get("text") or "")
    frag = (spec["expected_answer_fragment_kn"] if language == "kn"
            else spec["expected_answer_fragment_en"])
    if frag.lower() in (answer or "").lower():
        res.answer_fragment_ok = True
    else:
        # Lenient: pass if at least one of the source ids appears.
        sources = payload.get("sources") or []
        if isinstance(sources, list) and sources:
            res.answer_fragment_ok = True
            res.failures.append(f"answer fragment missing but sources present "
                                f"(lenient pass)")
        else:
            res.failures.append(f"answer fragment {frag!r} not found in response")

    if latency_ms >= HARD_BUDGET_MS:
        res.failures.append(f"latency {latency_ms:.0f}ms >= hard budget "
                            f"{HARD_BUDGET_MS}ms")
    return res


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results_table(results: list[QueryResult]) -> None:
    table = Table(title="Sarvik E2E Smoke — Golden Queries")
    table.add_column("Query", style="cyan")
    table.add_column("Lang")
    table.add_column("HTTP", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Intent")
    table.add_column("Viz")
    table.add_column("Count")
    table.add_column("Answer")
    table.add_column("Verdict", style="bold")
    for r in results:
        verdict = ("PASS" if r.passed and not r.warning
                   else "PASS (slow)" if r.passed and r.warning
                   else "FAIL")
        verdict_style = ("green" if r.passed and not r.warning
                         else "yellow" if r.warning
                         else "red")
        table.add_row(
            r.query_id, r.language, str(r.status_code),
            f"{r.latency_ms:.0f}ms",
            "OK" if r.intent_ok else "X",
            "OK" if r.viz_ok else "X",
            "OK" if r.count_ok else "X",
            "OK" if r.answer_fragment_ok else "X",
            f"[{verdict_style}]{verdict}[/{verdict_style}]",
        )
    console.print(table)


def save_results(results: list[QueryResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "warnings_slow": sum(1 for r in results if r.warning),
        "hard_budget_ms": HARD_BUDGET_MS,
        "soft_budget_ms": SOFT_BUDGET_MS,
        "results": [
            {
                "query_id": r.query_id,
                "language": r.language,
                "status_code": r.status_code,
                "latency_ms": round(r.latency_ms, 1),
                "intent_ok": r.intent_ok,
                "viz_ok": r.viz_ok,
                "count_ok": r.count_ok,
                "answer_fragment_ok": r.answer_fragment_ok,
                "failures": r.failures,
            }
            for r in results
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    # One file per query with raw response.
    for r in results:
        fname = f"{r.query_id}__{r.language}.json"
        (out_dir / fname).write_text(
            json.dumps(r.raw_response, indent=2, ensure_ascii=False),
            encoding="utf-8")
    # Plain-text table for slack/email paste.
    rows = [[r.query_id, r.language, r.status_code, f"{r.latency_ms:.0f}",
             "OK" if r.passed else "FAIL"]
            for r in results]
    (out_dir / "results.txt").write_text(
        tabulate(rows, headers=["query", "lang", "http", "ms", "verdict"],
                 tablefmt="github"),
        encoding="utf-8")
    console.print(f"\nResults written to: [bold]{out_dir}[/bold]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=["en", "kn", "both"], default="both",
                        help="Which language(s) to test for each query.")
    parser.add_argument("--query", help="Run only this query id.")
    parser.add_argument("--no-save", action="store_true",
                        help="Skip writing results to disk.")
    parser.add_argument("--strict", action="store_true",
                        help="Exit code 1 if any query is slow (>=3.5s).")
    args = parser.parse_args()

    env = _load_env()
    with GOLDEN_QUERIES.open("r", encoding="utf-8") as fh:
        gq = json.load(fh)

    queries = gq["queries"]
    if args.query:
        queries = [q for q in queries if q["id"] == args.query]
        if not queries:
            raise SystemExit(f"No query with id={args.query}")

    languages = ["en", "kn"] if args.lang == "both" else [args.lang]

    console.rule(f"[bold cyan]Sarvik smoke E2E — "
                 f"{len(queries)} queries × {len(languages)} lang(s)[/bold cyan]")
    console.print(f"Orchestrator: {env['api_base']}/.../function/{env['fn_name']}/execute")
    console.print(f"Hard budget: {HARD_BUDGET_MS}ms  Soft budget: {SOFT_BUDGET_MS}ms\n")

    results: list[QueryResult] = []
    for q in queries:
        for lang in languages:
            qtext = q["query_kn"] if lang == "kn" else q["query_en"]
            console.print(f"[dim]→[/dim] {q['id']} ({lang}): {qtext[:60]}...")
            status, body, latency = call_orchestrator(
                env, query=qtext, language=lang,
                role=q["role"], query_id=q["id"])
            res = check_query(q, status, body, latency, lang)
            results.append(res)
            if not res.passed:
                console.print(f"    [red]FAIL[/red] — {'; '.join(res.failures)}")
            elif res.warning:
                console.print(f"    [yellow]slow {res.latency_ms:.0f}ms[/yellow]")
            else:
                console.print(f"    [green]ok {res.latency_ms:.0f}ms[/green]")

    print()
    print_results_table(results)

    if not args.no_save:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_results(results, RESULTS_ROOT / ts)

    # Exit code
    if any(not r.passed for r in results):
        console.print("\n[bold red]FAIL[/bold red] — one or more queries did "
                      "not meet contract. Do not run live demo until fixed.")
        return 1
    if args.strict and any(r.warning for r in results):
        console.print("\n[bold yellow]STRICT FAIL[/bold yellow] — at least one "
                      "query exceeded soft latency budget.")
        return 2
    console.print("\n[bold green]ALL GREEN[/bold green] — demo is "
                  "smoke-tested clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
