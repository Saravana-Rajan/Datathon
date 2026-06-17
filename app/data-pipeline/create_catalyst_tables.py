"""
create_catalyst_tables.py — Provision Catalyst Data Store + NoSQL + Stratus for Sarvik.

WHY THIS EXISTS
---------------
`zcatalyst-sdk` (PyPI, latest 1.3.0) does NOT expose Data Store DDL — no
create_table(), no create_column(), no create_index(). The Console + the
Admin REST API (`api-console.catalyst.zoho.in/baas/v1/...`) are the only
programmatic paths. This script:

  1. Loads OAuth credentials from app/backend/.env (NEVER hard-coded).
  2. Mints a fresh access_token via the refresh_token grant.
  3. Calls the Catalyst REST API directly to create:
       Data Store:  firs, narrative_embeddings
       NoSQL    :  audit_logs, sessions, bias_review_queue
       Stratus  :  case-pdfs bucket
  4. Initializes the SDK (sanity-check that creds work end-to-end).
  5. Idempotent — if a table/bucket already exists we report SKIP, not FAIL.
  6. Prints a colored PASS/FAIL summary.

REQUIREMENTS
------------
  pip install zcatalyst-sdk==1.3.0 python-dotenv requests

USAGE
-----
  python create_catalyst_tables.py
  python create_catalyst_tables.py --dry-run        # show what would be created
  python create_catalyst_tables.py --only firs      # one resource only

If REST creation 401s (most likely cause: the Admin API on India DC requires a
ZSC scope your refresh token doesn't carry), the script falls back to printing
the exact Console steps from CATALYST_CONSOLE_SETUP.md and exits non-zero so CI
catches it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# 1. Env loading — credentials live in app/backend/.env (gitignored).
# --------------------------------------------------------------------------- #
try:
    from dotenv import load_dotenv
except ImportError:
    sys.stderr.write(
        "ERROR: python-dotenv missing. Install:  pip install python-dotenv\n"
    )
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


# --------------------------------------------------------------------------- #
# 2. Color helpers — work on cmd.exe / PowerShell / *nix.
# --------------------------------------------------------------------------- #
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    GREY = "\033[90m"


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if sys.platform == "win32":
        # Windows 10+ honors ANSI when virtual terminal is enabled — best-effort.
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:  # noqa: BLE001
            return False
    return sys.stdout.isatty()


if not _supports_color():
    for name in ("RESET", "BOLD", "GREEN", "RED", "YELLOW", "CYAN", "GREY"):
        setattr(C, name, "")


def ok(msg: str) -> None:
    print(f"  {C.GREEN}PASS{C.RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {C.YELLOW}SKIP{C.RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {C.RED}FAIL{C.RESET}  {msg}")


def info(msg: str) -> None:
    print(f"  {C.CYAN}INFO{C.RESET}  {msg}")


# --------------------------------------------------------------------------- #
# 3. Schemas — single source of truth, used by both creator and verifier.
# --------------------------------------------------------------------------- #
FIRS_COLUMNS: list[dict[str, Any]] = [
    {"name": "fir_no",            "type": "VARCHAR",  "length": 32,  "pk": True,  "mandatory": True,  "unique": True},
    {"name": "station_name",      "type": "VARCHAR",  "length": 128, "mandatory": True},
    {"name": "station_lat",       "type": "DECIMAL"},
    {"name": "station_lng",       "type": "DECIMAL"},
    {"name": "district",          "type": "VARCHAR",  "length": 64,  "mandatory": True},
    {"name": "date_registered",   "type": "DATE",     "mandatory": True},
    {"name": "time_registered",   "type": "VARCHAR",  "length": 16},
    {"name": "crime_type",        "type": "VARCHAR",  "length": 32,  "mandatory": True},
    {"name": "ipc_sections",      "type": "TEXT",     "description": "JSON list of section codes"},
    {"name": "location_lat",      "type": "DECIMAL"},
    {"name": "location_lng",      "type": "DECIMAL"},
    {"name": "location_text",     "type": "VARCHAR",  "length": 256},
    {"name": "complainant",       "type": "TEXT",     "description": "JSON object"},
    {"name": "accused",           "type": "TEXT",     "description": "JSON array"},
    {"name": "status",            "type": "VARCHAR",  "length": 32},
    {"name": "narrative",         "type": "TEXT"},
    {"name": "narrative_kannada", "type": "TEXT"},
]

EMBEDDINGS_COLUMNS: list[dict[str, Any]] = [
    {"name": "fir_no",     "type": "VARCHAR", "length": 32, "pk": True, "mandatory": True, "unique": True},
    {"name": "embedding",  "type": "TEXT",    "description": "JSON list of floats (768d Gemini)"},
    {"name": "text",       "type": "TEXT"},
    {"name": "crime_type", "type": "VARCHAR", "length": 32},
    {"name": "district",   "type": "VARCHAR", "length": 64},
    {"name": "date",       "type": "DATE"},
]

DATASTORE_TABLES = {
    "firs": FIRS_COLUMNS,
    "narrative_embeddings": EMBEDDINGS_COLUMNS,
}

NOSQL_TABLES = [
    {"name": "audit_logs",        "partition_key": "request_id", "sort_key": "step_index"},
    {"name": "sessions",          "partition_key": "session_id", "sort_key": "turn_index"},
    {"name": "bias_review_queue", "partition_key": "review_id",  "sort_key": None},
]

STRATUS_BUCKETS = ["case-pdfs"]


# --------------------------------------------------------------------------- #
# 4. Auth — mint an access_token from refresh_token.
# --------------------------------------------------------------------------- #
@dataclass
class Creds:
    org_id: str
    project_id: str
    api_base: str           # https://sarvik-60074155874.development.catalystserverless.in
    project_domain: str     # https://api-console.catalyst.zoho.in
    token_endpoint: str     # https://accounts.zoho.in/oauth/v2/token
    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str = ""
    expires_at: float = 0.0

    @classmethod
    def from_env(cls, allow_placeholder: bool = False) -> "Creds":
        required = [
            "CATALYST_ORG_ID", "CATALYST_PROJECT_ID", "CATALYST_API_BASE",
            "CATALYST_PROJECT_DOMAIN", "CATALYST_TOKEN_ENDPOINT",
            "CATALYST_CLIENT_ID", "CATALYST_CLIENT_SECRET", "CATALYST_REFRESH_TOKEN",
        ]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            sys.stderr.write(
                f"ERROR: missing env vars: {', '.join(missing)}\n"
                f"Source: {BACKEND_ENV}\n"
            )
            sys.exit(2)
        rt = os.environ["CATALYST_REFRESH_TOKEN"]
        if not allow_placeholder and (rt.startswith("REGENERATE_") or len(rt) < 20):
            sys.stderr.write(
                "ERROR: CATALYST_REFRESH_TOKEN is a placeholder. "
                "Run scripts/setup_env.sh to mint a real token, then retry.\n"
            )
            sys.exit(2)
        return cls(
            org_id=os.environ["CATALYST_ORG_ID"],
            project_id=os.environ["CATALYST_PROJECT_ID"],
            api_base=os.environ["CATALYST_API_BASE"].rstrip("/"),
            project_domain=os.environ["CATALYST_PROJECT_DOMAIN"].rstrip("/"),
            token_endpoint=os.environ["CATALYST_TOKEN_ENDPOINT"],
            client_id=os.environ["CATALYST_CLIENT_ID"],
            client_secret=os.environ["CATALYST_CLIENT_SECRET"],
            refresh_token=rt,
        )

    def refresh(self) -> None:
        resp = requests.post(
            self.token_endpoint,
            data={
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "access_token" not in payload:
            raise RuntimeError(f"Token refresh failed: {payload}")
        self.access_token = payload["access_token"]
        self.expires_at = time.time() + int(payload.get("expires_in", 3600)) - 60

    def auth_header(self) -> dict[str, str]:
        if not self.access_token or time.time() > self.expires_at:
            self.refresh()
        return {"Authorization": f"Zoho-oauthtoken {self.access_token}"}


# --------------------------------------------------------------------------- #
# 5. REST helpers — Catalyst Admin API endpoints.
# --------------------------------------------------------------------------- #
def admin_base(creds: Creds) -> str:
    """
    Catalyst admin REST root for a project.
      https://api-console.catalyst.zoho.in/baas/v1/project/<pid>
    """
    return f"{creds.project_domain}/baas/v1/project/{creds.project_id}"


def _request(
    method: str,
    url: str,
    creds: Creds,
    *,
    json_body: dict[str, Any] | list[Any] | None = None,
    expected: tuple[int, ...] = (200, 201, 202, 204),
) -> tuple[int, Any]:
    headers = creds.auth_header()
    headers["Content-Type"] = "application/json"
    resp = requests.request(
        method, url, headers=headers, json=json_body, timeout=30
    )
    body: Any
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return resp.status_code, body


# --------------------------------------------------------------------------- #
# 6. Reporter — tracks PASS / SKIP / FAIL for the final summary.
# --------------------------------------------------------------------------- #
@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def passed(self, what: str) -> None:
        self.created.append(what)
        ok(what)

    def skipped_existing(self, what: str) -> None:
        self.skipped.append(what)
        warn(f"{what} (already exists)")

    def errored(self, what: str, reason: str) -> None:
        self.failed.append((what, reason))
        fail(f"{what} — {reason}")

    def summary(self) -> int:
        bar = "=" * 68
        print(f"\n{C.BOLD}{bar}{C.RESET}")
        print(f"{C.BOLD}  CATALYST PROVISIONING SUMMARY{C.RESET}")
        print(f"{C.BOLD}{bar}{C.RESET}")
        print(f"  {C.GREEN}Created : {len(self.created)}{C.RESET}")
        for x in self.created:
            print(f"     + {x}")
        print(f"  {C.YELLOW}Skipped : {len(self.skipped)}{C.RESET}")
        for x in self.skipped:
            print(f"     ~ {x}")
        print(f"  {C.RED}Failed  : {len(self.failed)}{C.RESET}")
        for what, reason in self.failed:
            print(f"     ! {what}: {reason}")
        print(f"{C.BOLD}{bar}{C.RESET}\n")
        if self.failed:
            print(
                f"{C.YELLOW}Some resources could not be created via the REST API.{C.RESET}\n"
                f"Open {C.CYAN}CATALYST_CONSOLE_SETUP.md{C.RESET} and create them by hand.\n"
            )
            return 1
        return 0


# --------------------------------------------------------------------------- #
# 7. Creators — one function per resource type.
# --------------------------------------------------------------------------- #
def _datastore_payload(table_name: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
    """Catalyst Admin API expects column definitions in this shape."""
    cols = []
    for c in columns:
        col: dict[str, Any] = {
            "column_name": c["name"],
            "data_type": c["type"],
            "is_mandatory": c.get("mandatory", False),
            "is_unique": c.get("unique", False),
        }
        if "length" in c:
            col["max_length"] = c["length"]
        if c.get("pk"):
            col["is_primary"] = True
        cols.append(col)
    return {"table_name": table_name, "columns": cols}


def create_datastore_table(
    creds: Creds, table_name: str, columns: list[dict[str, Any]], report: Report
) -> None:
    url = f"{admin_base(creds)}/table"
    status, body = _request("POST", url, creds, json_body=_datastore_payload(table_name, columns))
    label = f"Data Store table '{table_name}'"
    if status in (200, 201):
        report.passed(label)
        return
    # Catalyst returns a structured error code in `body['data']['error_code']`.
    msg = json.dumps(body)[:240] if not isinstance(body, str) else body[:240]
    if status == 409 or "DUPLICATE" in msg.upper() or "ALREADY" in msg.upper():
        report.skipped_existing(label)
        return
    report.errored(label, f"HTTP {status}: {msg}")


def create_nosql_table(
    creds: Creds, spec: dict[str, Any], report: Report
) -> None:
    name = spec["name"]
    payload: dict[str, Any] = {
        "table_name": name,
        "partition_key": {"column_name": spec["partition_key"], "data_type": "STRING"},
    }
    if spec.get("sort_key"):
        payload["sort_key"] = {"column_name": spec["sort_key"], "data_type": "NUMBER"}
    url = f"{admin_base(creds)}/nosqltable"
    status, body = _request("POST", url, creds, json_body=payload)
    label = f"NoSQL table '{name}'"
    if status in (200, 201):
        report.passed(label)
        return
    msg = json.dumps(body)[:240] if not isinstance(body, str) else body[:240]
    if status == 409 or "DUPLICATE" in msg.upper() or "ALREADY" in msg.upper():
        report.skipped_existing(label)
        return
    report.errored(label, f"HTTP {status}: {msg}")


def create_stratus_bucket(creds: Creds, name: str, report: Report) -> None:
    # Stratus uses a slightly different admin path.
    url = f"{admin_base(creds)}/stratus/bucket"
    status, body = _request(
        "POST", url, creds,
        json_body={"bucket_name": name, "object_versioning": False, "encryption": True},
    )
    label = f"Stratus bucket '{name}'"
    if status in (200, 201):
        report.passed(label)
        return
    msg = json.dumps(body)[:240] if not isinstance(body, str) else body[:240]
    if status == 409 or "DUPLICATE" in msg.upper() or "ALREADY" in msg.upper():
        report.skipped_existing(label)
        return
    report.errored(label, f"HTTP {status}: {msg}")


# --------------------------------------------------------------------------- #
# 8. SDK sanity check — confirm creds are usable beyond REST.
# --------------------------------------------------------------------------- #
def sdk_sanity_check(creds: Creds) -> bool:
    try:
        import zcatalyst_sdk
    except ImportError:
        info("zcatalyst-sdk not installed — REST-only mode (install with `pip install zcatalyst-sdk==1.3.0`).")
        return False
    try:
        app = zcatalyst_sdk.initialize(
            credentials={
                "project_id": creds.project_id,
                "project_domain": creds.project_domain,
                "environment": os.getenv("CATALYST_ENVIRONMENT", "Development"),
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": creds.refresh_token,
            }
        )
        # Touch one method to confirm the auth chain.
        _ = app.datastore()
        info(f"SDK initialized OK for project {creds.project_id}")
        return True
    except Exception as exc:  # noqa: BLE001
        info(f"SDK init non-fatal warning: {exc}")
        return False


# --------------------------------------------------------------------------- #
# 9. Main
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="Show planned actions, don't call the API.")
    p.add_argument(
        "--only",
        choices=("firs", "narrative_embeddings", "audit_logs", "sessions",
                 "bias_review_queue", "case-pdfs"),
        help="Create one resource only (useful for retries).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    creds = Creds.from_env(allow_placeholder=args.dry_run)

    print(f"\n{C.BOLD}== Sarvik / Catalyst -- provisioning =={C.RESET}")
    print(f"  Project ID  : {creds.project_id}")
    print(f"  Org ID      : {creds.org_id}")
    print(f"  Admin base  : {creds.project_domain}")
    print(f"  Env file    : {BACKEND_ENV}")
    print()

    if args.dry_run:
        info("DRY RUN — no API calls will be made.")
        print()
        for name in DATASTORE_TABLES:
            if args.only and args.only != name:
                continue
            print(f"  [datastore] would create '{name}' ({len(DATASTORE_TABLES[name])} columns)")
        for spec in NOSQL_TABLES:
            if args.only and args.only != spec["name"]:
                continue
            sort = spec.get("sort_key") or "—"
            print(f"  [nosql]     would create '{spec['name']}' (pk={spec['partition_key']}, sort={sort})")
        for b in STRATUS_BUCKETS:
            if args.only and args.only != b:
                continue
            print(f"  [stratus]   would create bucket '{b}'")
        print()
        return 0

    # Mint token early so failures here are reported clearly.
    try:
        creds.refresh()
        ok(f"OAuth refresh — token minted ({creds.token_endpoint})")
    except Exception as exc:  # noqa: BLE001
        fail(f"OAuth refresh failed — {exc}")
        print(
            f"\n{C.YELLOW}Refresh token rejected. Re-mint via api-console.zoho.in "
            f"and update CATALYST_REFRESH_TOKEN in {BACKEND_ENV}.{C.RESET}\n"
        )
        return 1

    # SDK sanity (optional — never blocks REST path).
    sdk_sanity_check(creds)

    report = Report()

    # Data Store tables
    print(f"\n{C.BOLD}-- Data Store --{C.RESET}")
    for name, cols in DATASTORE_TABLES.items():
        if args.only and args.only != name:
            continue
        try:
            create_datastore_table(creds, name, cols, report)
        except Exception as exc:  # noqa: BLE001
            report.errored(f"Data Store table '{name}'", str(exc))

    # NoSQL tables
    print(f"\n{C.BOLD}-- NoSQL --{C.RESET}")
    for spec in NOSQL_TABLES:
        if args.only and args.only != spec["name"]:
            continue
        try:
            create_nosql_table(creds, spec, report)
        except Exception as exc:  # noqa: BLE001
            report.errored(f"NoSQL table '{spec['name']}'", str(exc))

    # Stratus buckets
    print(f"\n{C.BOLD}-- Stratus --{C.RESET}")
    for b in STRATUS_BUCKETS:
        if args.only and args.only != b:
            continue
        try:
            create_stratus_bucket(creds, b, report)
        except Exception as exc:  # noqa: BLE001
            report.errored(f"Stratus bucket '{b}'", str(exc))

    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
