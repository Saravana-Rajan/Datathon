"""SQL safety guardrails for the KSP Saathi SQL generator.

The contract:
  - Only one statement per call.
  - Only SELECT (or WITH ... SELECT) — no DDL, no DML, no admin verbs.
  - Tables referenced must be in the whitelist (see schema.ALLOWED_TABLES).
  - No inline comments (`--`, `#`, `/* ... */`) — they're commonly used to
    smuggle past naive validators; we strip + reject anything with them.
  - No `;` chaining (one statement per request).
  - No PostGIS function names — Catalyst Data Store doesn't support them and
    we have a bounding-box rewrite path in index.py instead.

`is_safe_sql(sql)` returns `(ok, reasons)`. Reasons is empty when ok=True.
Callers MUST treat ok=False as a hard reject (return a 400 / raise) — never
"clean up and run anyway". The validator is intentionally strict; false
positives are fine because the generator can retry, false negatives are not.

This file is import-safe — no Catalyst / Gemini imports — so test_safety can
run anywhere.
"""

from __future__ import annotations

import re
from typing import Iterable

from schema import ALLOWED_TABLES


# ---------------------------------------------------------------------------
# Forbidden keywords. Matched as whole words, case-insensitive.
# ---------------------------------------------------------------------------

# Any of these in the statement → reject. We're deliberately broad: even if
# the underlying driver wouldn't honour it, we don't want generated SQL to
# advertise we tried.
FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "DELETE",
    "DROP",
    "TRUNCATE",
    "UPDATE",
    "INSERT",
    "REPLACE",
    "MERGE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "ATTACH",
    "DETACH",
    "EXEC",
    "EXECUTE",
    "CALL",
    "COPY",
    "VACUUM",
    "ANALYZE",
    "PRAGMA",
    "SET",
    "RESET",
    "LOAD",
    "UNLOAD",
    "LOCK",
    "UNLOCK",
    "INTO",          # blocks `SELECT ... INTO new_table`
    "OUTFILE",       # blocks `SELECT ... INTO OUTFILE`
    "DUMPFILE",
    "SLEEP",         # time-based blind injection
    "BENCHMARK",     # MySQL DoS
    "WAITFOR",
    "XP_CMDSHELL",
    "INFORMATION_SCHEMA",
    "PG_CATALOG",
    "PG_SLEEP",
)

# PostGIS / geospatial verbs we deliberately don't support in raw SQL.
# index.py rewrites these into bounding-box predicates before execution.
POSTGIS_FUNCTIONS: tuple[str, ...] = (
    "ST_DWITHIN",
    "ST_DISTANCE",
    "ST_DISTANCESPHERE",
    "ST_INTERSECTS",
    "ST_CONTAINS",
    "ST_COVERS",
    "ST_WITHIN",
    "ST_BUFFER",
    "ST_GEOMFROMTEXT",
    "ST_MAKEPOINT",
    "ST_POINT",
)


# Statements that count as "starts a query". Anything else is rejected.
_QUERY_PREFIXES: tuple[str, ...] = ("SELECT", "WITH")


# Regex: identifier after FROM / JOIN. Pulls the first token, ignoring
# schema qualifiers (`public.firs` → `firs`).
_TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([\"`\[]?[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?[\"`\]]?)",
    re.IGNORECASE,
)


def _strip_quotes(ident: str) -> str:
    return ident.strip('"`[] ').split(".")[-1].lower()


def _has_comment(sql: str) -> bool:
    """True if the SQL contains `--`, `#`, or `/* ... */` style comments."""
    if "--" in sql or "/*" in sql or "*/" in sql:
        return True
    # `#` is a MySQL inline comment. We don't expect column names with `#`.
    if re.search(r"(^|\s)#", sql):
        return True
    return False


def _multiple_statements(sql: str) -> bool:
    """True if more than one non-empty statement is present.

    We allow a single trailing `;` but reject anything after it.
    """
    parts = [p.strip() for p in sql.split(";")]
    non_empty = [p for p in parts if p]
    return len(non_empty) > 1


def _whole_word_match(haystack_upper: str, needle_upper: str) -> bool:
    return re.search(rf"\b{re.escape(needle_upper)}\b", haystack_upper) is not None


def _extract_tables(sql: str) -> list[str]:
    return [_strip_quotes(m.group(1)) for m in _TABLE_REF_RE.finditer(sql)]


def _starts_with_query(sql_upper: str) -> bool:
    stripped = sql_upper.lstrip("( \t\n\r")
    return any(stripped.startswith(p) for p in _QUERY_PREFIXES)


def is_safe_sql(sql: str) -> tuple[bool, list[str]]:
    """Validate a candidate SQL string.

    Returns `(True, [])` if safe; `(False, [reason, ...])` otherwise. Reasons
    are short, human-readable strings suitable for the API `warnings` field
    and the audit log.
    """
    reasons: list[str] = []

    if not isinstance(sql, str) or not sql.strip():
        return False, ["empty_sql"]

    raw = sql.strip()
    upper = raw.upper()

    # 1. Single statement only.
    if _multiple_statements(raw):
        reasons.append("multiple_statements_not_allowed")

    # 2. Must start with SELECT / WITH.
    if not _starts_with_query(upper):
        reasons.append("only_select_or_with_allowed")

    # 3. No comments — they're a common injection vector.
    if _has_comment(raw):
        reasons.append("comments_not_allowed")

    # 4. No forbidden keywords (whole-word match).
    for kw in FORBIDDEN_KEYWORDS:
        if _whole_word_match(upper, kw):
            reasons.append(f"forbidden_keyword:{kw.lower()}")

    # 5. No PostGIS — Catalyst Data Store can't run it. index.py rewrites
    #    geospatial intent into bounding boxes BEFORE calling this validator,
    #    so by the time we see SQL here it should be PostGIS-free.
    for fn in POSTGIS_FUNCTIONS:
        if _whole_word_match(upper, fn):
            reasons.append(f"postgis_function_not_supported:{fn.lower()}")

    # 6. Every referenced table must be whitelisted.
    tables = _extract_tables(raw)
    if not tables:
        reasons.append("no_table_reference_found")
    for tbl in tables:
        if tbl not in ALLOWED_TABLES:
            reasons.append(f"table_not_whitelisted:{tbl}")

    return (len(reasons) == 0), reasons


def assert_safe(sql: str) -> None:
    """Raise `UnsafeSQLError` with the joined reasons if `sql` is unsafe."""
    ok, reasons = is_safe_sql(sql)
    if not ok:
        raise UnsafeSQLError(reasons)


class UnsafeSQLError(ValueError):
    """Raised when a candidate SQL string fails the safety check."""

    def __init__(self, reasons: Iterable[str]) -> None:
        self.reasons = list(reasons)
        super().__init__("unsafe_sql: " + ", ".join(self.reasons))
