"""
verify_catalyst_setup.py — Post-provision smoke test for the Sarvik Catalyst project.

WHAT IT CHECKS (in order)
-------------------------
  1. OAuth token can be minted from the refresh token in app/backend/.env
  2. zcatalyst-sdk imports and initializes
  3. Data Store tables exist:  firs, narrative_embeddings
  4. NoSQL tables exist:        audit_logs, sessions, bias_review_queue
  5. Stratus bucket exists:     case-pdfs
  6. Round-trip into `firs`: insert one test row, read it back, delete it.
     (proves writes work AND the schema accepted our payload)

OUTPUTS
-------
  "READY for data load"   — every check passed and round-trip succeeded
  "MISSING: [...]"        — one or more resources are missing or broken

Exits 0 on READY, 1 on MISSING.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    sys.stderr.write("ERROR: python-dotenv missing. Install:  pip install python-dotenv\n")
    sys.exit(2)

try:
    import requests
except ImportError:
    sys.stderr.write("ERROR: requests missing. Install:  pip install requests\n")
    sys.exit(2)


HERE = Path(__file__).resolve().parent
BACKEND_ENV = HERE.parent / "backend" / ".env"
if not BACKEND_ENV.exists():
    sys.stderr.write(f"ERROR: env file not found at {BACKEND_ENV}\n")
    sys.exit(2)
load_dotenv(BACKEND_ENV)


REQUIRED_DATASTORE = ["firs", "narrative_embeddings"]
REQUIRED_NOSQL = ["audit_logs", "sessions", "bias_review_queue"]
REQUIRED_BUCKETS = ["case-pdfs"]


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
class C:
    RESET = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"


if not sys.stdout.isatty():
    for n in ("RESET", "GREEN", "RED", "YELLOW", "BOLD", "CYAN"):
        setattr(C, n, "")


def line(prefix: str, color: str, msg: str) -> None:
    print(f"  {color}{prefix}{C.RESET}  {msg}")


# --------------------------------------------------------------------------- #
# Credentials + token
# --------------------------------------------------------------------------- #
def env(k: str) -> str:
    v = os.getenv(k)
    if not v:
        sys.stderr.write(f"ERROR: env var {k} not set in {BACKEND_ENV}\n")
        sys.exit(2)
    return v


def get_token() -> tuple[str, dict[str, str]]:
    rt = env("CATALYST_REFRESH_TOKEN")
    if rt.startswith("REGENERATE_") or len(rt) < 20:
        sys.stderr.write("ERROR: CATALYST_REFRESH_TOKEN is a placeholder. Re-mint and retry.\n")
        sys.exit(2)
    resp = requests.post(
        env("CATALYST_TOKEN_ENDPOINT"),
        data={
            "refresh_token": rt,
            "client_id": env("CATALYST_CLIENT_ID"),
            "client_secret": env("CATALYST_CLIENT_SECRET"),
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    tok = resp.json().get("access_token")
    if not tok:
        raise RuntimeError(f"No access_token in refresh response: {resp.text[:200]}")
    return tok, {"Authorization": f"Zoho-oauthtoken {tok}", "Content-Type": "application/json"}


def admin_url(path: str) -> str:
    base = env("CATALYST_PROJECT_DOMAIN").rstrip("/")
    pid = env("CATALYST_PROJECT_ID")
    return f"{base}/baas/v1/project/{pid}{path}"


# --------------------------------------------------------------------------- #
# Existence checks via REST (the SDK has list_tables but it's flaky on India DC)
# --------------------------------------------------------------------------- #
def list_datastore_tables(headers: dict[str, str]) -> list[str]:
    r = requests.get(admin_url("/table"), headers=headers, timeout=20)
    if r.status_code != 200:
        return []
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        name = item.get("table_name") or item.get("name")
        if name:
            out.append(name)
    return out


def list_nosql_tables(headers: dict[str, str]) -> list[str]:
    r = requests.get(admin_url("/nosqltable"), headers=headers, timeout=20)
    if r.status_code != 200:
        return []
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        name = item.get("table_name") or item.get("name")
        if name:
            out.append(name)
    return out


def list_stratus_buckets(headers: dict[str, str]) -> list[str]:
    r = requests.get(admin_url("/stratus/bucket"), headers=headers, timeout=20)
    if r.status_code != 200:
        return []
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        name = item.get("bucket_name") or item.get("name")
        if name:
            out.append(name)
    return out


# --------------------------------------------------------------------------- #
# Round trip — insert / read / delete one row in `firs`
# --------------------------------------------------------------------------- #
TEST_FIR_NO = f"VERIFY-{uuid.uuid4().hex[:8].upper()}"


def round_trip_firs() -> tuple[bool, str]:
    try:
        import zcatalyst_sdk
    except ImportError:
        return False, "zcatalyst-sdk not installed"

    try:
        app = zcatalyst_sdk.initialize(
            credentials={
                "project_id": env("CATALYST_PROJECT_ID"),
                "project_domain": env("CATALYST_PROJECT_DOMAIN"),
                "environment": os.getenv("CATALYST_ENVIRONMENT", "Development"),
                "client_id": env("CATALYST_CLIENT_ID"),
                "client_secret": env("CATALYST_CLIENT_SECRET"),
                "refresh_token": env("CATALYST_REFRESH_TOKEN"),
            }
        )
        table = app.datastore().table("firs")

        row: dict[str, Any] = {
            "fir_no": TEST_FIR_NO,
            "station_name": "VERIFY-STATION",
            "district": "Bengaluru Urban",
            "date_registered": "2026-06-17",
            "crime_type": "VERIFY",
            "status": "TEST",
            "narrative": "Smoke-test row inserted by verify_catalyst_setup.py — safe to delete.",
            "ipc_sections": json.dumps(["000"]),
            "complainant": json.dumps({"name": "verify"}),
            "accused": json.dumps([]),
        }
        # Insert
        if hasattr(table, "insert_row"):
            inserted = table.insert_row(row)
        else:
            inserted = table.insert_rows([row])

        # Read back via ZCQL.
        zcql = app.zcql()
        rows = zcql.execute_zcql_query(
            f"SELECT fir_no, status FROM firs WHERE fir_no = '{TEST_FIR_NO}'"
        ) or []
        found = False
        for r in rows:
            payload = r.get("firs") if isinstance(r, dict) else None
            if payload and payload.get("fir_no") == TEST_FIR_NO:
                found = True
                break
        if not found:
            return False, "insert returned OK but row not visible via ZCQL"

        # Delete — grab ROWID. Catalyst returns it on insert.
        rowid = None
        if isinstance(inserted, dict):
            rowid = inserted.get("ROWID") or inserted.get("rowid")
        elif isinstance(inserted, list) and inserted:
            first = inserted[0]
            if isinstance(first, dict):
                rowid = first.get("ROWID") or first.get("rowid")
        if rowid:
            try:
                table.delete_row(rowid)
            except Exception:  # noqa: BLE001
                # ZCQL fallback delete.
                zcql.execute_zcql_query(
                    f"DELETE FROM firs WHERE fir_no = '{TEST_FIR_NO}'"
                )
        else:
            zcql.execute_zcql_query(
                f"DELETE FROM firs WHERE fir_no = '{TEST_FIR_NO}'"
            )
        return True, "insert + read + delete OK"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    print(f"\n{C.BOLD}== Catalyst verification =={C.RESET}")
    print(f"  Env file: {BACKEND_ENV}\n")

    missing: list[str] = []

    # 1. Token
    try:
        _token, headers = get_token()
        line("PASS", C.GREEN, "OAuth token minted from refresh_token")
    except Exception as exc:  # noqa: BLE001
        line("FAIL", C.RED, f"OAuth refresh failed — {exc}")
        print(f"\n{C.RED}MISSING: [oauth]{C.RESET}\n")
        return 1

    # 2. Data Store tables
    ds_present = list_datastore_tables(headers)
    for t in REQUIRED_DATASTORE:
        if t in ds_present:
            line("PASS", C.GREEN, f"Data Store table '{t}' exists")
        else:
            line("FAIL", C.RED, f"Data Store table '{t}' MISSING")
            missing.append(f"datastore:{t}")

    # 3. NoSQL tables
    nq_present = list_nosql_tables(headers)
    for t in REQUIRED_NOSQL:
        if t in nq_present:
            line("PASS", C.GREEN, f"NoSQL table '{t}' exists")
        else:
            line("FAIL", C.RED, f"NoSQL table '{t}' MISSING")
            missing.append(f"nosql:{t}")

    # 4. Stratus buckets
    buckets = list_stratus_buckets(headers)
    for b in REQUIRED_BUCKETS:
        if b in buckets:
            line("PASS", C.GREEN, f"Stratus bucket '{b}' exists")
        else:
            line("FAIL", C.RED, f"Stratus bucket '{b}' MISSING")
            missing.append(f"stratus:{b}")

    # 5. Round trip — only if `firs` exists.
    if "firs" in ds_present:
        ok_, detail = round_trip_firs()
        if ok_:
            line("PASS", C.GREEN, f"Round-trip on firs — {detail}")
        else:
            line("FAIL", C.RED, f"Round-trip on firs — {detail}")
            missing.append("round-trip:firs")
    else:
        line("SKIP", C.YELLOW, "Round-trip skipped (firs table not present)")

    print()
    if not missing:
        print(f"  {C.BOLD}{C.GREEN}READY for data load{C.RESET}\n")
        return 0
    print(f"  {C.BOLD}{C.RED}MISSING: {missing}{C.RESET}\n")
    print(
        f"  Fix: re-run {C.CYAN}python create_catalyst_tables.py{C.RESET}, or follow\n"
        f"       {C.CYAN}CATALYST_CONSOLE_SETUP.md{C.RESET} to create the missing resources by hand.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
