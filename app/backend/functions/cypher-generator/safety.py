"""Cypher safety guardrails for the KSP Saathi cypher-generator.

Contract (mirrors functions/sql-generator/safety.py):
  - Exactly one statement per call.
  - READ-ONLY clauses only: MATCH, OPTIONAL MATCH, WITH, WHERE, RETURN,
    ORDER BY, LIMIT, UNWIND, DISTINCT, SKIP.
  - Hard reject any write / admin verb: CREATE, DELETE, DETACH, SET, MERGE,
    REMOVE, DROP, CALL, LOAD CSV, FOREACH.
  - No inline comments (`//`, `/* ... */`).
  - Variable-length traversals must be bounded AND <= MAX_REL_DEPTH hops.
    Anything bigger gets capped (not rejected) — the user still gets an
    answer, just a less ambitious one, with a warning surfaced upstream.
  - LIMIT is mandatory. If the LLM forgot one, `enforce_limit` adds the
    default. Two separate functions so callers can decide whether to mutate.

`is_safe_cypher(cy)` returns `(ok, reasons, fixed_cypher)`. When ok=True the
caller should use `fixed_cypher` (it may have a depth cap or LIMIT applied).
When ok=False the caller MUST reject — never "clean up and run anyway".
"""

from __future__ import annotations

import re
from typing import Iterable

from schema import (
    ALLOWED_REL_TYPES,
    DEFAULT_LIMIT,
    MAX_REL_DEPTH,
)


# ---------------------------------------------------------------------------
# Forbidden clauses / procedures. Whole-word, case-insensitive.
# ---------------------------------------------------------------------------

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "CREATE",
    "DELETE",
    "DETACH",
    "SET",
    "MERGE",
    "REMOVE",
    "DROP",
    "FOREACH",
    "LOAD",          # LOAD CSV
    "USING",         # USING PERIODIC COMMIT
    "CALL",          # blocks db.* / apoc.* / gds.* procedures
    "GRANT",
    "REVOKE",
    "START",         # legacy write
    "TERMINATE",
)

# Allowed clause starters — used to spot suspicious unknown clauses.
ALLOWED_CLAUSES: tuple[str, ...] = (
    "MATCH",
    "OPTIONAL",       # OPTIONAL MATCH
    "RETURN",
    "WITH",
    "WHERE",
    "ORDER",          # ORDER BY
    "LIMIT",
    "SKIP",
    "UNWIND",
    "DISTINCT",
)


# Regex helpers --------------------------------------------------------------

# Match `*1..N` / `*..N` / `*N..M` variable-length range expressions.
_REL_RANGE_RE = re.compile(r"\*\s*(\d+)?\s*\.\.\s*(\d+)?")

# Match an unbounded `*` (no range) — also dangerous.
_REL_UNBOUNDED_RE = re.compile(r"\*(?!\s*\d)")

# Match a LIMIT clause anywhere in the statement.
_LIMIT_RE = re.compile(r"\bLIMIT\b\s+\d+", re.IGNORECASE)

# Match `[:REL_TYPE]` / `[r:REL_TYPE]` / `[r:REL_TYPE*1..3]` patterns to
# extract relationship type names and validate them against the whitelist.
_REL_TYPE_RE = re.compile(r"\[\s*[A-Za-z_]\w*\s*:\s*([A-Z_][A-Z_0-9|]*)", re.IGNORECASE)
_REL_TYPE_ONLY_RE = re.compile(r"\[\s*:\s*([A-Z_][A-Z_0-9|]*)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _has_comment(cypher: str) -> bool:
    """True if the Cypher contains `//` or `/* ... */` style comments."""
    return "//" in cypher or "/*" in cypher or "*/" in cypher


def _multiple_statements(cypher: str) -> bool:
    parts = [p.strip() for p in cypher.split(";")]
    non_empty = [p for p in parts if p]
    return len(non_empty) > 1


def _whole_word_match(haystack_upper: str, needle_upper: str) -> bool:
    return re.search(rf"\b{re.escape(needle_upper)}\b", haystack_upper) is not None


def _starts_with_read_clause(cypher_upper: str) -> bool:
    stripped = cypher_upper.lstrip("( \t\n\r")
    return stripped.startswith("MATCH") or stripped.startswith("OPTIONAL") or stripped.startswith("WITH") or stripped.startswith("UNWIND")


def _extract_rel_types(cypher: str) -> list[str]:
    """Return relationship type names referenced in `[:TYPE]` / `[r:TYPE]`."""
    found: list[str] = []
    for match in _REL_TYPE_RE.finditer(cypher):
        # The pattern `[a-z:TYPE]` might also match `[node:Label]` outside a
        # relationship. Guard by checking the prior character.
        start = match.start()
        # Look back two chars; if it's a `(`, this is a node, skip it.
        prev = cypher[max(0, start - 1):start]
        if prev == "(":
            continue
        for typ in match.group(1).split("|"):
            t = typ.strip().upper()
            if t:
                found.append(t)
    for match in _REL_TYPE_ONLY_RE.finditer(cypher):
        start = match.start()
        prev = cypher[max(0, start - 1):start]
        if prev == "(":
            continue
        for typ in match.group(1).split("|"):
            t = typ.strip().upper()
            if t:
                found.append(t)
    return found


# ---------------------------------------------------------------------------
# Depth cap + LIMIT enforcement (mutating helpers)
# ---------------------------------------------------------------------------

def cap_depth(cypher: str, max_depth: int = MAX_REL_DEPTH) -> tuple[str, list[str]]:
    """Cap variable-length traversals to `max_depth` hops.

    Examples:
        `*1..10` → `*1..3`
        `*..7`   → `*..3`
        `*`      → `*1..3`  (unbounded becomes safe-bounded)

    Returns `(rewritten_cypher, warnings)`. Warnings are added once per cap.
    """
    warnings: list[str] = []

    def _cap_range(match: re.Match[str]) -> str:
        low_raw, high_raw = match.group(1), match.group(2)
        low = int(low_raw) if low_raw else None
        high = int(high_raw) if high_raw else None

        new_low = low
        new_high = high
        capped = False
        if high is None or high > max_depth:
            new_high = max_depth
            capped = True
        if low is not None and low > max_depth:
            new_low = max_depth
            capped = True

        if capped:
            warnings.append(f"depth_capped_to_{max_depth}")

        low_str = str(new_low) if new_low is not None else ""
        high_str = str(new_high) if new_high is not None else ""
        return f"*{low_str}..{high_str}"

    out = _REL_RANGE_RE.sub(_cap_range, cypher)

    # Replace any unbounded `*` (no following digits) with `*1..N`.
    def _bound_unbounded(match: re.Match[str]) -> str:
        warnings.append(f"unbounded_traversal_bounded_to_{max_depth}")
        return f"*1..{max_depth}"

    out = _REL_UNBOUNDED_RE.sub(_bound_unbounded, out)
    return out, warnings


def enforce_limit(cypher: str, default_limit: int = DEFAULT_LIMIT) -> tuple[str, list[str]]:
    """Append `LIMIT default_limit` if none is present.

    We append at the very end of the statement (stripping any trailing `;`)
    rather than trying to splice it into a nested WITH/RETURN. The driver
    runs the result fine — Cypher's grammar accepts LIMIT after RETURN.
    """
    warnings: list[str] = []
    if _LIMIT_RE.search(cypher):
        return cypher, warnings
    base = cypher.rstrip().rstrip(";").rstrip()
    warnings.append(f"limit_injected:{default_limit}")
    return f"{base} LIMIT {default_limit}", warnings


# ---------------------------------------------------------------------------
# Top-level validator
# ---------------------------------------------------------------------------

def is_safe_cypher(cypher: str) -> tuple[bool, list[str], str]:
    """Validate + safely fix up a candidate Cypher string.

    Returns `(ok, reasons, fixed_cypher)`. Reasons is empty when ok=True.

    Fixes applied even on the success path:
      - depth cap (anything > MAX_REL_DEPTH is rewritten, with a warning
        appended to `reasons`);
      - LIMIT injection (if missing).

    Hard rejects (ok=False):
      - empty / non-string input
      - multiple statements
      - any forbidden keyword
      - comments present
      - relationship type outside the whitelist
      - statement doesn't start with a read clause
    """
    reasons: list[str] = []

    if not isinstance(cypher, str) or not cypher.strip():
        return False, ["empty_cypher"], ""

    raw = cypher.strip()
    upper = raw.upper()

    # 1. Single statement.
    if _multiple_statements(raw):
        reasons.append("multiple_statements_not_allowed")

    # 2. No comments.
    if _has_comment(raw):
        reasons.append("comments_not_allowed")

    # 3. Must start with a read clause.
    if not _starts_with_read_clause(upper):
        reasons.append("only_read_clauses_allowed")

    # 4. No forbidden keywords (whole-word match).
    for kw in FORBIDDEN_KEYWORDS:
        if _whole_word_match(upper, kw):
            reasons.append(f"forbidden_keyword:{kw.lower()}")

    # 5. Relationship types must be whitelisted.
    rel_types = _extract_rel_types(raw)
    for rt in rel_types:
        if rt not in ALLOWED_REL_TYPES:
            reasons.append(f"rel_type_not_whitelisted:{rt}")

    if reasons:
        # Don't bother fixing up unsafe Cypher.
        return False, reasons, raw

    # 6. Apply safe fix-ups.
    fixed, depth_warnings = cap_depth(raw)
    fixed, limit_warnings = enforce_limit(fixed)
    reasons.extend(depth_warnings)
    reasons.extend(limit_warnings)

    return True, reasons, fixed


def assert_safe(cypher: str) -> str:
    """Raise `UnsafeCypherError` if unsafe; otherwise return the fixed Cypher."""
    ok, reasons, fixed = is_safe_cypher(cypher)
    if not ok:
        raise UnsafeCypherError(reasons)
    return fixed


class UnsafeCypherError(ValueError):
    """Raised when a candidate Cypher string fails the safety check."""

    def __init__(self, reasons: Iterable[str]) -> None:
        self.reasons = list(reasons)
        super().__init__("unsafe_cypher: " + ", ".join(self.reasons))


__all__ = [
    "is_safe_cypher",
    "assert_safe",
    "cap_depth",
    "enforce_limit",
    "UnsafeCypherError",
    "FORBIDDEN_KEYWORDS",
    "ALLOWED_CLAUSES",
]
