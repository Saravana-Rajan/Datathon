#!/usr/bin/env python3
"""
Sarvik (ksp-saathi) — Prewarm
==============================

Keeps Catalyst Functions warm during the 10 minutes leading up to a live demo.
Calls every critical function once per minute (default 10 cycles) with a
"warmup" flag the function honours as a no-op fast path.

This is belt-and-suspenders alongside Catalyst `min-instances=1`. We've all
seen the first call after a deploy take 8 seconds — never the second. Don't
let that happen during a finale.

Run BEFORE demo (start ~12 min ahead):
    python prewarm.py                 # 10 cycles, 60s gap, all functions
    python prewarm.py --cycles 15     # extended warm
    python prewarm.py --interval 30   # tighter cadence
    python prewarm.py --only orchestrator,intent_router

Env:
    CATALYST_API_BASE, CATALYST_PROJECT_ID, CATALYST_AUTH_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

console = Console()

# These match the function names in app/backend/functions/. Keep in sync
# when new functions are added that need warmth before the demo.
DEFAULT_FUNCTIONS = [
    "orchestrator",
    "intent-router",
    "sql-generator",
    "cypher-generator",
    "rag-retriever",
    "synthesizer",
    "audit-logger",
    "pdf-exporter",
]


@dataclass
class WarmConfig:
    api_base: str
    project_id: str
    auth_token: str

    @classmethod
    def from_env(cls) -> "WarmConfig":
        load_dotenv(REPO_ROOT / "app" / ".env", override=False)
        load_dotenv(REPO_ROOT / ".env", override=False)
        api_base = os.environ.get("CATALYST_API_BASE")
        if not api_base:
            raise SystemExit("CATALYST_API_BASE not set. See app/.env.example.")
        return cls(
            api_base=api_base.rstrip("/"),
            project_id=os.environ.get("CATALYST_PROJECT_ID", ""),
            auth_token=os.environ.get("CATALYST_AUTH_TOKEN", ""),
        )


def ping(cfg: WarmConfig, fn: str, http: httpx.Client) -> tuple[int, float]:
    url = (f"{cfg.api_base}/baas/v1/project/{cfg.project_id}"
           f"/function/{fn}/execute")
    headers = {
        "Authorization": f"Zoho-oauthtoken {cfg.auth_token}",
        "Content-Type": "application/json",
    }
    payload = {"warmup": True, "client": "prewarm", "ts": int(time.time())}
    t0 = time.perf_counter()
    try:
        r = http.post(url, json=payload, headers=headers, timeout=15.0)
        status = r.status_code
    except httpx.RequestError as exc:
        return -1, (time.perf_counter() - t0) * 1000
    return status, (time.perf_counter() - t0) * 1000


_stop = False
def _handle_signal(signum, frame):  # noqa: ARG001
    global _stop
    _stop = True
    console.print("\n[yellow]signal received — finishing current cycle then "
                  "stopping...[/yellow]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycles", type=int, default=10,
                        help="How many warmup cycles to run (default 10).")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between cycles (default 60).")
    parser.add_argument("--only", type=str,
                        help="Comma-separated subset of function names to warm.")
    parser.add_argument("--quiet", action="store_true",
                        help="Less output per cycle.")
    args = parser.parse_args()

    cfg = WarmConfig.from_env()
    functions = ([f.strip() for f in args.only.split(",")] if args.only
                 else DEFAULT_FUNCTIONS)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    console.rule(f"[bold cyan]Sarvik prewarm — "
                 f"{len(functions)} fns × {args.cycles} cycles "
                 f"× {args.interval}s[/bold cyan]")
    console.print("Functions: " + ", ".join(functions))
    console.print("Start at: " + datetime.now().isoformat(timespec="seconds"))
    console.print()

    cold_misses: dict[str, int] = {fn: 0 for fn in functions}
    with httpx.Client() as http:
        for cycle in range(1, args.cycles + 1):
            if _stop:
                break
            stamp = datetime.now().strftime("%H:%M:%S")
            console.print(f"[bold]cycle {cycle}/{args.cycles}[/bold] @ {stamp}")
            for fn in functions:
                if _stop:
                    break
                status, latency = ping(cfg, fn, http)
                slow = latency > 2000
                col = ("green" if 200 <= status < 300 and not slow
                       else "yellow" if 200 <= status < 300 and slow
                       else "red")
                if slow:
                    cold_misses[fn] += 1
                if not args.quiet or status != 200 or slow:
                    console.print(f"  [{col}]{fn:<20}[/{col}] "
                                  f"http={status} {latency:.0f}ms"
                                  f"{' (cold?)' if slow else ''}")
            if cycle < args.cycles and not _stop:
                time.sleep(args.interval)

    console.rule("[bold]Prewarm summary[/bold]")
    for fn, n_slow in cold_misses.items():
        flag = "ok" if n_slow == 0 else f"[yellow]{n_slow} slow cycles[/yellow]"
        console.print(f"  {fn:<20} {flag}")
    if any(v > 0 for v in cold_misses.values()):
        console.print("\n[yellow]Note:[/yellow] some functions still went cold. "
                      "Verify Catalyst min-instances=1 is set in console.")
    else:
        console.print("\n[green]All functions hot. Safe to run live demo.[/green]")

    console.print("End at: " + datetime.now().isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
