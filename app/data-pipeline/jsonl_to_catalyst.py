"""
jsonl_to_catalyst.py — Convert synthetic FIR JSONL into a Catalyst Data Store-compatible
format and (optionally) upload rows via the Zoho Catalyst Python SDK.

Designed for KSP Saathi (Datathon 2026, Challenge 01). Idempotent: rows whose
`fir_no` already exists in the Catalyst Data Store will be skipped.

USAGE
-----
  # Convert JSONL → CSV (flattened, nested fields JSON-stringified)
  python jsonl_to_catalyst.py --input ../../data/firs.jsonl --mode csv --table firs

  # Upload to Catalyst Data Store (requires env vars below)
  python jsonl_to_catalyst.py --input ../../data/firs.jsonl --mode upload --table firs

  # Custom batch size + output CSV path
  python jsonl_to_catalyst.py --input ../../data/firs.jsonl --mode csv \\
      --output firs.csv --batch-size 100

ENVIRONMENT (upload mode)
-------------------------
  CATALYST_PROJECT_ID          numeric project id from console.catalyst.zoho.in
  CATALYST_PROJECT_KEY         project key (used by the SDK)
  CATALYST_PROJECT_DOMAIN      e.g. https://api.catalyst.zoho.in   (India DC)
  CATALYST_ENVIRONMENT         development | production            (default: development)
  CATALYST_USER_ID             numeric user id (often required for auth context)
  CATALYST_CLIENT_ID           OAuth client id (for self-client / refresh-token auth)
  CATALYST_CLIENT_SECRET       OAuth client secret
  CATALYST_REFRESH_TOKEN       OAuth refresh token
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "ERROR: tqdm is required. Install with:  pip install -r requirements.txt\n"
    )
    raise

# Field order locked to data/README.md schema reference.
FIELDS: list[str] = [
    "fir_no",
    "station_name",
    "station_lat",
    "station_lng",
    "district",
    "date_registered",
    "time_registered",
    "crime_type",
    "ipc_sections",
    "location_lat",
    "location_lng",
    "location_text",
    "complainant",
    "accused",
    "victims",
    "modus_operandi",
    "modus_operandi_kannada",
    "investigating_officer",
    "status",
    "linked_fir_nos",
    "narrative",
    "narrative_kannada",
]

# Nested fields that need to be JSON-stringified for CSV / TEXT-column upload.
NESTED_FIELDS: set[str] = {
    "ipc_sections",
    "complainant",
    "accused",
    "victims",
    "investigating_officer",
    "linked_fir_nos",
}

LOG = logging.getLogger("jsonl_to_catalyst")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
@dataclass
class RunReport:
    total_read: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_bad: int = 0
    errors: list[str] = field(default_factory=list)
    batches_uploaded: int = 0
    started_at: float = field(default_factory=time.time)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        LOG.warning(msg)

    def elapsed(self) -> float:
        return time.time() - self.started_at

    def print_summary(self) -> None:
        bar = "=" * 60
        print(f"\n{bar}\n RUN SUMMARY\n{bar}")
        print(f"  Rows read              : {self.total_read:,}")
        print(f"  Rows written / uploaded: {self.written:,}")
        print(f"  Skipped (already in DS): {self.skipped_existing:,}")
        print(f"  Skipped (bad / parse)  : {self.skipped_bad:,}")
        print(f"  Errors                 : {len(self.errors):,}")
        print(f"  Batches uploaded       : {self.batches_uploaded:,}")
        print(f"  Elapsed                : {self.elapsed():.1f} s")
        if self.errors:
            preview = "\n    ".join(self.errors[:5])
            print(f"\n  First errors:\n    {preview}")
            if len(self.errors) > 5:
                print(f"    ... and {len(self.errors) - 5} more")
        print(bar)


# --------------------------------------------------------------------------- #
# I/O helpers
# --------------------------------------------------------------------------- #
def count_lines(path: Path) -> int:
    """Cheap line counter for the tqdm total."""
    with path.open("rb") as f:
        return sum(1 for _ in f)


def iter_jsonl(path: Path, report: RunReport) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            report.total_read += 1
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:
                report.skipped_bad += 1
                report.add_error(f"line {lineno}: JSON decode failed — {exc}")


def flatten_row(rec: dict[str, Any]) -> dict[str, Any]:
    """Stringify nested fields so the row maps cleanly to TEXT / JSON columns."""
    flat: dict[str, Any] = {}
    for key in FIELDS:
        value = rec.get(key)
        if key in NESTED_FIELDS:
            flat[key] = json.dumps(value, ensure_ascii=False) if value is not None else ""
        else:
            flat[key] = value if value is not None else ""
    return flat


# --------------------------------------------------------------------------- #
# CSV mode
# --------------------------------------------------------------------------- #
def run_csv_mode(input_path: Path, output_path: Path) -> RunReport:
    report = RunReport()
    total = count_lines(input_path)
    LOG.info("CSV mode: %s → %s (%d lines)", input_path, output_path, total)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        for rec in tqdm(
            iter_jsonl(input_path, report),
            total=total,
            desc="Flattening",
            unit="row",
            ncols=88,
        ):
            try:
                if "fir_no" not in rec or not rec["fir_no"]:
                    report.skipped_bad += 1
                    report.add_error(f"row missing fir_no: {json.dumps(rec)[:120]}")
                    continue
                writer.writerow(flatten_row(rec))
                report.written += 1
            except Exception as exc:  # noqa: BLE001
                report.skipped_bad += 1
                report.add_error(f"flatten failed for {rec.get('fir_no')}: {exc}")

    print(f"\n  ✔ Wrote {report.written:,} rows to {output_path}")
    return report


# --------------------------------------------------------------------------- #
# Catalyst SDK helpers
# --------------------------------------------------------------------------- #
def init_catalyst_app():
    """Initialize a Catalyst SDK app from environment variables.

    Returns the initialized `app` object or raises with a helpful message.
    """
    try:
        import zcatalyst_sdk
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Upload mode requires zcatalyst-sdk. Install:  pip install -r requirements.txt"
        ) from exc

    required = [
        "CATALYST_PROJECT_ID",
        "CATALYST_PROJECT_KEY",
        "CATALYST_PROJECT_DOMAIN",
    ]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise SystemExit(
            "Missing required Catalyst env vars: " + ", ".join(missing)
            + "\n  See header docstring for the full list."
        )

    # zcatalyst_sdk.initialize() picks up env vars automatically when running
    # inside a Catalyst Function context. Outside of that context (CLI here)
    # we initialize with an explicit credentials dict so the SDK has what it
    # needs for self-client / refresh-token auth.
    credentials = {
        "project_id": os.environ["CATALYST_PROJECT_ID"],
        "project_key": os.environ["CATALYST_PROJECT_KEY"],
        "project_domain": os.environ["CATALYST_PROJECT_DOMAIN"],
        "environment": os.getenv("CATALYST_ENVIRONMENT", "development"),
    }
    # Auth credentials (optional in some setups, required for external CLI use)
    for k_env, k_creds in (
        ("CATALYST_USER_ID", "user_id"),
        ("CATALYST_CLIENT_ID", "client_id"),
        ("CATALYST_CLIENT_SECRET", "client_secret"),
        ("CATALYST_REFRESH_TOKEN", "refresh_token"),
    ):
        if os.getenv(k_env):
            credentials[k_creds] = os.environ[k_env]

    app = zcatalyst_sdk.initialize(credentials=credentials)
    LOG.info(
        "Catalyst SDK initialized (project=%s env=%s)",
        credentials["project_id"],
        credentials["environment"],
    )
    return app


def fetch_existing_fir_nos(app, table_name: str) -> set[str]:
    """Query Catalyst Data Store upfront for every fir_no that already exists.

    Uses ZCQL via app.zcql() so the result set stays small (one column).
    Falls back to an empty set on error (idempotency-by-merge becomes
    idempotency-by-insert-skip-on-409 in that case).
    """
    existing: set[str] = set()
    try:
        zcql = app.zcql()
        # Pull fir_no in pages of 10k (Data Store ZCQL limit ~10k rows / query).
        page_size = 10_000
        offset = 0
        while True:
            query = (
                f'SELECT fir_no FROM "{table_name}" '
                f"LIMIT {page_size} OFFSET {offset}"
            )
            rows = zcql.execute_zcql_query(query) or []
            if not rows:
                break
            for row in rows:
                # ZCQL rows come back as { table_name: { col: value } }
                payload = row.get(table_name) if isinstance(row, dict) else None
                if payload and payload.get("fir_no"):
                    existing.add(str(payload["fir_no"]))
            if len(rows) < page_size:
                break
            offset += page_size
        LOG.info("Existing rows in %s: %d", table_name, len(existing))
    except Exception as exc:  # noqa: BLE001
        LOG.warning(
            "Could not pre-fetch existing fir_no set (%s). "
            "Will rely on per-row insert error handling for idempotency.",
            exc,
        )
    return existing


def insert_batch(table, batch: list[dict[str, Any]]) -> tuple[int, list[str]]:
    """Insert a batch into Catalyst Data Store. Returns (inserted_count, errors)."""
    errors: list[str] = []
    try:
        # Newer SDK: insert_rows; older variants: insert_row in a loop.
        if hasattr(table, "insert_rows"):
            table.insert_rows(batch)
        else:  # pragma: no cover - SDK API drift fallback
            for row in batch:
                table.insert_row(row)
        return len(batch), errors
    except Exception as exc:  # noqa: BLE001
        # Whole-batch failure: degrade to per-row to localize the bad record.
        LOG.warning("Batch insert failed (%s) — retrying row-by-row", exc)
        inserted = 0
        for row in batch:
            try:
                if hasattr(table, "insert_row"):
                    table.insert_row(row)
                else:
                    table.insert_rows([row])
                inserted += 1
            except Exception as row_exc:  # noqa: BLE001
                errors.append(
                    f"insert failed for fir_no={row.get('fir_no')}: {row_exc}"
                )
        return inserted, errors


# --------------------------------------------------------------------------- #
# Upload mode
# --------------------------------------------------------------------------- #
def run_upload_mode(
    input_path: Path,
    table_name: str,
    batch_size: int,
) -> RunReport:
    report = RunReport()
    app = init_catalyst_app()
    datastore = app.datastore()
    table = datastore.table(table_name)

    LOG.info("Fetching existing fir_no set from Data Store...")
    existing = fetch_existing_fir_nos(app, table_name)

    total = count_lines(input_path)
    LOG.info("Upload mode: %s → table %s (%d lines, batch=%d)",
             input_path, table_name, total, batch_size)

    batch: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal batch
        if not batch:
            return
        inserted, errs = insert_batch(table, batch)
        report.written += inserted
        report.batches_uploaded += 1
        for e in errs:
            report.add_error(e)
        # Anything not inserted is counted as bad.
        report.skipped_bad += len(batch) - inserted
        batch = []

    for rec in tqdm(
        iter_jsonl(input_path, report),
        total=total,
        desc="Uploading",
        unit="row",
        ncols=88,
    ):
        fir_no = rec.get("fir_no")
        if not fir_no:
            report.skipped_bad += 1
            report.add_error(f"row missing fir_no: {json.dumps(rec)[:120]}")
            continue

        if fir_no in existing:
            report.skipped_existing += 1
            continue

        try:
            batch.append(flatten_row(rec))
        except Exception as exc:  # noqa: BLE001
            report.skipped_bad += 1
            report.add_error(f"flatten failed for {fir_no}: {exc}")
            continue

        # Track in `existing` so a duplicate inside the same JSONL is also
        # caught (defense in depth).
        existing.add(str(fir_no))

        if len(batch) >= batch_size:
            flush()

    flush()
    print(f"\n  ✔ Uploaded {report.written:,} rows to table '{table_name}'")
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert FIR JSONL → Catalyst Data Store format (CSV or live upload).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Path to firs.jsonl (one FIR JSON per line).",
    )
    p.add_argument(
        "--mode", "-m",
        choices=("csv", "upload"),
        required=True,
        help="csv = write flattened CSV.  upload = insert into Catalyst Data Store.",
    )
    p.add_argument(
        "--table", "-t",
        default="firs",
        help="Catalyst Data Store table name (default: firs).",
    )
    p.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="CSV output path (default: <input-stem>.csv next to the input).",
    )
    p.add_argument(
        "--batch-size", "-b",
        type=int,
        default=100,
        help="Rows per Catalyst insert call (default: 100).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.input.exists():
        LOG.error("Input file not found: %s", args.input)
        return 2

    banner = "─" * 60
    print(f"\n{banner}")
    print(f"  KSP Saathi — FIR → Catalyst Data Store")
    print(f"  Mode  : {args.mode}")
    print(f"  Input : {args.input}")
    print(f"  Table : {args.table}")
    if args.mode == "csv":
        out_path = args.output or args.input.with_suffix(".csv")
        print(f"  Output: {out_path}")
    else:
        print(f"  Batch : {args.batch_size}")
    print(f"{banner}\n")

    if args.mode == "csv":
        out_path = args.output or args.input.with_suffix(".csv")
        report = run_csv_mode(args.input, out_path)
    else:
        report = run_upload_mode(args.input, args.table, args.batch_size)

    report.print_summary()
    # Exit non-zero if every row failed (likely a config problem worth surfacing in CI).
    return 0 if report.written > 0 or report.total_read == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
