"""
schema_init.py — Initialize the `firs` table in the Catalyst Data Store.

This script does TWO things:

1. If `zcatalyst_sdk` is installed AND Catalyst env vars are set, it attempts to
   create the table + indexes programmatically via the SDK.

2. Whether or not the SDK path succeeds, it ALWAYS prints copy-paste-ready,
   step-by-step instructions for the Catalyst Console (the SDK currently
   restricts DDL on some plans, so the Console path is the reliable fallback).

USAGE
-----
  python schema_init.py                      # default: prints console steps
  python schema_init.py --create             # tries SDK first, falls back to print
  python schema_init.py --table firs         # custom table name

ENVIRONMENT (--create mode)
---------------------------
  See jsonl_to_catalyst.py header for the full env-var list.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Literal

LOG = logging.getLogger("schema_init")

ColumnType = Literal["VARCHAR", "TEXT", "BIGINT", "INT", "DOUBLE", "DATE", "DATETIME"]


@dataclass
class Column:
    name: str
    type: ColumnType
    length: int | None = None
    is_mandatory: bool = False
    is_unique: bool = False
    description: str = ""

    def ddl_hint(self) -> str:
        t = self.type
        if self.length:
            t = f"{t}({self.length})"
        flags = []
        if self.is_mandatory:
            flags.append("NOT NULL")
        if self.is_unique:
            flags.append("UNIQUE")
        flag_s = " " + " ".join(flags) if flags else ""
        comment = f"   -- {self.description}" if self.description else ""
        return f"  {self.name:<28} {t}{flag_s}{comment}"


# Schema mirrors data/README.md and data/generate_synthetic_firs.py exactly.
COLUMNS: list[Column] = [
    Column("fir_no",                "VARCHAR", 32,  True, True,
           "Primary identifier: <STATION_CODE>/<YEAR>/<COUNTER>"),
    Column("station_name",          "VARCHAR", 128, True, False,
           "Indexed for station-scoped queries"),
    Column("station_lat",           "DOUBLE",  None, False, False),
    Column("station_lng",           "DOUBLE",  None, False, False),
    Column("district",              "VARCHAR", 64,  True, False,
           "Indexed for district roll-ups"),
    Column("date_registered",       "DATE",    None, True, False,
           "Indexed for trend / time-series queries"),
    Column("time_registered",       "VARCHAR", 16,  False, False),
    Column("crime_type",            "VARCHAR", 32,  True, False,
           "Indexed; enum (see data/README.md)"),
    Column("ipc_sections",          "TEXT",    None, False, False,
           "JSON-stringified array (e.g. [\"379\",\"411\"])"),
    Column("location_lat",          "DOUBLE",  None, False, False,
           "Indexed for H3 hex hotspot lookups"),
    Column("location_lng",          "DOUBLE",  None, False, False,
           "Indexed for H3 hex hotspot lookups"),
    Column("location_text",         "VARCHAR", 256, False, False),
    Column("complainant",           "TEXT",    None, False, False,
           "JSON-stringified object"),
    Column("accused",               "TEXT",    None, False, False,
           "JSON-stringified array of objects"),
    Column("victims",               "TEXT",    None, False, False,
           "JSON-stringified array of objects"),
    Column("modus_operandi",        "TEXT",    None, False, False),
    Column("modus_operandi_kannada","TEXT",    None, False, False,
           "Unicode Kannada — Data Store must be utf8mb4"),
    Column("investigating_officer", "TEXT",    None, False, False),
    Column("status",                "VARCHAR", 32,  True, False),
    Column("linked_fir_nos",        "TEXT",    None, False, False,
           "JSON-stringified array of related fir_no values"),
    Column("narrative",             "TEXT",    None, False, False,
           "English summary (chunked for RAG by embed_narratives.py)"),
    Column("narrative_kannada",     "TEXT",    None, False, False,
           "Kannada summary (Unicode)"),
]

# Indexes the conversational AI use-case actually queries on. Composite at the
# bottom is what powers the canonical "district X, crime Y, last N days" query.
INDEXES: list[tuple[str, list[str], bool]] = [
    ("idx_firs_fir_no",            ["fir_no"],            True),   # unique
    ("idx_firs_date_registered",   ["date_registered"],   False),
    ("idx_firs_crime_type",        ["crime_type"],        False),
    ("idx_firs_station_name",      ["station_name"],      False),
    ("idx_firs_district",          ["district"],          False),
    ("idx_firs_location_lat",      ["location_lat"],      False),
    ("idx_firs_location_lng",      ["location_lng"],      False),
    ("idx_firs_dist_crime_date",   ["district", "crime_type", "date_registered"], False),
]


# --------------------------------------------------------------------------- #
# Console / DDL hint printer (always runs)
# --------------------------------------------------------------------------- #
def print_console_instructions(table_name: str) -> None:
    bar = "═" * 68
    print(f"\n{bar}")
    print(f"  CATALYST CONSOLE — STEP-BY-STEP TABLE CREATION  ({table_name})")
    print(f"{bar}")
    print(
        f"""
  1. Open console.catalyst.zoho.in  →  select your project (KSP Saathi).
  2. In the left nav: Cloud Scale → Data Store.
  3. Click  + New Table .  Set:
       • Table Name : {table_name}
       • Description: Karnataka FIR records (synthetic + real)
       • Modified Time / Created Time : ON
  4. Add the following columns IN ORDER (match types exactly):
"""
    )
    print(f"  -- DDL hint --")
    print(f"  CREATE TABLE {table_name} (")
    for col in COLUMNS:
        print(col.ddl_hint())
    print("  );")

    print(f"\n  5. After creating the table, add these INDEXES")
    print(f"     (Data Store → {table_name} → Indexes tab):")
    print()
    for idx_name, cols, is_unique in INDEXES:
        kind = "UNIQUE" if is_unique else "      "
        col_list = ", ".join(cols)
        print(f"     {kind}  {idx_name:<28} ON ({col_list})")

    print(
        f"""
  6. Confirm character set is utf8mb4 (Catalyst default — needed for the
     Kannada Unicode columns `narrative_kannada` and `modus_operandi_kannada`).

  7. Verify by running this query in the Data Store Query Console:
       SELECT COUNT(*) FROM {table_name};
     Expect: 0  (empty table).

  8. Now you can run:
       python jsonl_to_catalyst.py --input ../../data/firs.jsonl \\
              --mode upload --table {table_name}
"""
    )
    print(f"{bar}\n")


# --------------------------------------------------------------------------- #
# Optional: SDK-based create attempt
# --------------------------------------------------------------------------- #
def try_create_via_sdk(table_name: str) -> bool:
    """Best-effort SDK creation. Returns True if it succeeded."""
    try:
        import zcatalyst_sdk  # noqa: F401
    except ImportError:
        LOG.warning("zcatalyst-sdk not installed — skipping SDK create attempt.")
        return False

    required = ["CATALYST_PROJECT_ID", "CATALYST_PROJECT_KEY", "CATALYST_PROJECT_DOMAIN"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        LOG.warning(
            "Skipping SDK create — missing env vars: %s",
            ", ".join(missing),
        )
        return False

    try:
        # Import lazily so import-time failures don't break the print-only path.
        from jsonl_to_catalyst import init_catalyst_app  # type: ignore
    except ImportError:
        LOG.warning("Could not import init_catalyst_app from jsonl_to_catalyst.py")
        return False

    try:
        app = init_catalyst_app()
    except SystemExit as exc:
        LOG.warning("Catalyst init failed: %s", exc)
        return False

    # NOTE on the Catalyst SDK surface:
    # As of zcatalyst-sdk 1.x, Data Store DDL (table + index creation) is not
    # exposed as a public Python API — table creation lives in the Console and
    # the Admin REST API. We attempt the documented `admin().data_store()` path
    # if it exists; if not, fall back gracefully to the print path.
    try:
        admin = getattr(app, "admin", None)
        if admin is None or not hasattr(admin(), "data_store"):
            LOG.info(
                "SDK build does not expose DDL methods — use the Console path "
                "printed above. This is expected on most plans."
            )
            return False
        ds_admin = admin().data_store()
        ds_admin.create_table(
            {
                "table_name": table_name,
                "columns": [
                    {
                        "column_name": c.name,
                        "data_type": c.type,
                        "max_length": c.length,
                        "is_mandatory": c.is_mandatory,
                        "is_unique": c.is_unique,
                    }
                    for c in COLUMNS
                ],
            }
        )
        LOG.info("Table %s created via SDK", table_name)
        for idx_name, cols, is_unique in INDEXES:
            try:
                ds_admin.create_index(
                    {
                        "table_name": table_name,
                        "index_name": idx_name,
                        "columns": cols,
                        "is_unique": is_unique,
                    }
                )
                LOG.info("Index %s created", idx_name)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("Index %s — %s (create manually in console)", idx_name, exc)
        return True
    except Exception as exc:  # noqa: BLE001
        LOG.warning("SDK DDL not available (%s). Use the console steps above.", exc)
        return False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--table", "-t", default="firs", help="Table name (default: firs).")
    p.add_argument(
        "--create",
        action="store_true",
        help="Attempt programmatic creation via SDK before printing console steps.",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    sdk_ok = False
    if args.create:
        sdk_ok = try_create_via_sdk(args.table)
        if sdk_ok:
            print(f"\n  ✔ Table `{args.table}` created via Catalyst SDK.")
            print("    Verify in console.catalyst.zoho.in → Data Store.\n")

    # Always print the console fallback so Person A has a runbook regardless.
    print_console_instructions(args.table)

    if not sdk_ok:
        print("  NOTE: SDK auto-create did not run (or is unsupported on this plan).")
        print("        Follow the console steps above — they are the source of truth.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
