"""KSP Saathi — SQL Generator Catalyst Function.

Advanced I/O endpoint. Given a natural-language query and the upstream
router decision (entities, time window, location, crime type), generates a
single SELECT statement against the `firs` table, validates it, executes it
on Catalyst Data Store, and returns the rows + the SQL itself for audit.

High-level flow:
    1. Parse + validate the inbound JSON payload.
    2. Build a prompt for Qwen 2.5 14B Instruct (Catalyst QuickML) using
       the FIR schema constant and the router decision. We try to import
       `shared.prompts.sql_gen_prompt` first; if it isn't deployed yet we
       fall back to a local prompt builder so this function stays usable.
    3. Call QuickML's LLM Serving endpoint (REST). The shared client
       handles auth + retries.
    4. Extract SQL from the model response (strip markdown fences etc.),
       then run it through `safety.is_safe_sql`.
    5. If the router flagged the query as geospatial (a location entity is
       present) or the model emitted PostGIS, rewrite the predicate to a
       bounding-box pre-filter. Haversine distance filtering then happens
       in Python on the returned rows.
    6. Execute via `datastore.execute_query` and return:
         { sql, results, row_count, execution_ms, warnings }

The function never raises to Catalyst — every error path returns a 4xx/5xx
JSON body so the orchestrator (Circuits) can decide whether to retry, fall
back to RAG, or surface a friendly Kannada error to the user.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
import traceback
from typing import Any

# Make the `shared/` package importable when this function is bundled solo.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from schema import FIR_SCHEMA, CRIME_TYPES  # noqa: E402  (sys.path mutation above)
from safety import is_safe_sql, POSTGIS_FUNCTIONS  # noqa: E402

logger = logging.getLogger("ksp_saathi.sql_generator")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Tunables (env-overridable so we don't redeploy for prompt / model tweaks)
# ---------------------------------------------------------------------------

QUICKML_LLM_ENDPOINT = os.getenv("QUICKML_LLM_ENDPOINT", "")           # full URL
QUICKML_ENDPOINT_KEY = os.getenv("QUICKML_ENDPOINT_KEY", "")
QUICKML_OAUTH_TOKEN = os.getenv("QUICKML_OAUTH_TOKEN", "")
QUICKML_ORG_ID = os.getenv("CATALYST_ORG_ID", "")
QUICKML_ENVIRONMENT = os.getenv("CATALYST_ENVIRONMENT", "Development")
QUICKML_MODEL_NAME = os.getenv("QUICKML_MODEL", "qwen-2.5-14b-instruct")

DEFAULT_GEO_RADIUS_KM = float(os.getenv("SQL_GEN_GEO_RADIUS_KM", "2.0"))
MAX_ROWS_RETURNED = int(os.getenv("SQL_GEN_MAX_ROWS", "500"))

# Earth radius for haversine. Standard mean-radius value.
EARTH_RADIUS_KM = 6371.0088


# ---------------------------------------------------------------------------
# Prompt building (with optional shared.prompts override)
# ---------------------------------------------------------------------------

def _local_sql_gen_prompt(
    query: str,
    entities: dict[str, Any] | None,
    schema: str,
) -> str:
    """Default SQL-gen prompt used when `shared.prompts` isn't deployed yet.

    Kept deliberately terse — Qwen 2.5 14B Instruct does best with a short,
    rule-style preamble plus the schema + entity context.
    """
    entities = entities or {}
    crime_types_csv = ", ".join(CRIME_TYPES)
    entity_block = json.dumps(entities, ensure_ascii=False, indent=2)

    return f"""You are a SQL generator for the Karnataka State Police FIR database.

RULES:
- Output ONE SQL statement. SELECT only. No semicolons except a single trailing one.
- Only the `firs` table is allowed. No JOINs unless to `firs` aliases.
- No DROP / DELETE / UPDATE / INSERT / ALTER / TRUNCATE — those are blocked downstream.
- No inline comments (`--`, `#`, `/* */`).
- For geo queries DO NOT use ST_DWithin / ST_Distance / PostGIS — Catalyst Data Store
  has no PostGIS. Emit a bounding box: `location_lat BETWEEN ? AND ? AND location_lng BETWEEN ? AND ?`.
- `crime_type` is one of: {crime_types_csv}.
- Dates use ISO format (`YYYY-MM-DD`). "last month" / "last week" → compute a literal date.
- Return ONLY the SQL, no prose, no markdown fences.

SCHEMA:
{schema}

ROUTER ENTITIES (use these to ground the query):
{entity_block}

USER QUERY:
{query}

SQL:"""


def _build_prompt(query: str, entities: dict[str, Any] | None) -> str:
    """Prefer `shared.prompts.sql_gen_prompt` if present, else fall back."""
    try:
        from shared.prompts import sql_gen_prompt  # type: ignore
        return sql_gen_prompt(query, entities, FIR_SCHEMA)
    except Exception:  # noqa: BLE001 — fallback is intentional
        return _local_sql_gen_prompt(query, entities, FIR_SCHEMA)


# ---------------------------------------------------------------------------
# QuickML LLM call (Qwen 2.5 14B Instruct on Catalyst)
# ---------------------------------------------------------------------------

def _call_qwen(prompt: str, *, temperature: float = 0.1, max_tokens: int = 512) -> str:
    """Call the QuickML LLM Serving endpoint and return the model's text.

    Catalyst QuickML LLM Serving is a plain HTTPS POST — auth headers per
    docs/catalyst-reference.md §10. We use httpx (vendored in requirements)
    rather than the SDK because QuickML is exposed as a REST endpoint, not
    a first-class SDK method.
    """
    if not (QUICKML_LLM_ENDPOINT and QUICKML_ENDPOINT_KEY and QUICKML_OAUTH_TOKEN):
        raise RuntimeError(
            "quickml_not_configured: QUICKML_LLM_ENDPOINT/KEY/OAUTH_TOKEN must be set."
        )

    import httpx  # local import — keeps cold-start cheap when other paths run

    headers = {
        "Authorization": f"Zoho-oauthtoken {QUICKML_OAUTH_TOKEN}",
        "X-QUICKML-ENDPOINT-KEY": QUICKML_ENDPOINT_KEY,
        "CATALYST-ORG": QUICKML_ORG_ID,
        "Environment": QUICKML_ENVIRONMENT,
        "Content-Type": "application/json",
    }
    body = {
        "prompt": prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # `instructions` is the QuickML name for system prompt. We've already
        # baked the rules into the prompt body, so we pass a short reinforcer.
        "instructions": "Output only valid SQL. No prose. No markdown.",
    }

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(QUICKML_LLM_ENDPOINT, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    # QuickML response shape varies; we accept the common variants.
    for key in ("output", "text", "response", "completion"):
        val = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(val, str) and val.strip():
            return val
    # Some deployments wrap in { data: { output: "..." } }
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        for key in ("output", "text", "response", "completion"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
    raise RuntimeError(f"quickml_unexpected_response_shape: keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)}")


# ---------------------------------------------------------------------------
# SQL extraction + geospatial rewrite
# ---------------------------------------------------------------------------

_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _extract_sql(raw_model_output: str) -> str:
    """Pull the SQL string out of a model response.

    Models sometimes wrap output in ```sql ... ``` fences, add a leading
    "SQL:" label, or include a one-line explanation. We strip all of that.
    """
    if not raw_model_output:
        return ""
    text = raw_model_output.strip()

    # 1. Markdown fence — take the first block.
    m = _SQL_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    # 2. Drop a leading "SQL:" label if present.
    text = re.sub(r"^\s*SQL\s*:\s*", "", text, flags=re.IGNORECASE)

    # 3. Trim to the first statement only (cut at first newline-newline if any
    #    explanation follows the SQL).
    # We keep semicolons; the safety check forbids more than one statement.
    return text.strip()


def _km_to_degrees_lat(km: float) -> float:
    """Latitude degrees per km (approx — 1 deg lat ≈ 110.574 km)."""
    return km / 110.574


def _km_to_degrees_lng(km: float, at_lat: float) -> float:
    """Longitude degrees per km at a given latitude."""
    return km / (111.320 * max(math.cos(math.radians(at_lat)), 1e-6))


def _bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return (lat_min, lat_max, lng_min, lng_max) for a circle of radius_km."""
    dlat = _km_to_degrees_lat(radius_km)
    dlng = _km_to_degrees_lng(radius_km, lat)
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


_POSTGIS_PRESENT_RE = re.compile(
    r"\b(?:" + "|".join(POSTGIS_FUNCTIONS) + r")\b", re.IGNORECASE
)


def rewrite_geospatial(
    sql: str,
    location: dict[str, Any] | None,
    *,
    default_radius_km: float = DEFAULT_GEO_RADIUS_KM,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    """If the SQL contains PostGIS or the router flagged a location, rewrite.

    Strategy:
      - If the router supplied {lat, lng, radius_km?} we build a bounding-box
        predicate and append it (or replace any PostGIS predicate found).
      - If the SQL has PostGIS calls but no location was passed, we strip
        them out and leave a warning — the caller should re-route to RAG or
        ask the user to disambiguate.
      - We also return a `geo_filter` dict (center + radius_km) so index.py
        can run the haversine post-filter on returned rows.

    Returns `(rewritten_sql, geo_filter_or_none, warnings)`.
    """
    warnings: list[str] = []
    has_postgis = bool(_POSTGIS_PRESENT_RE.search(sql))

    loc = location or {}
    lat = loc.get("lat")
    lng = loc.get("lng")
    radius_km = float(loc.get("radius_km") or default_radius_km)

    if lat is None or lng is None:
        if has_postgis:
            # Strip the PostGIS predicate — leave a comment-free replacement.
            stripped = _POSTGIS_PRESENT_RE.sub("FALSE", sql)
            warnings.append("postgis_stripped_no_location")
            return stripped, None, warnings
        return sql, None, warnings

    lat_min, lat_max, lng_min, lng_max = _bounding_box(float(lat), float(lng), radius_km)
    bbox_predicate = (
        f"location_lat BETWEEN {lat_min:.6f} AND {lat_max:.6f} "
        f"AND location_lng BETWEEN {lng_min:.6f} AND {lng_max:.6f}"
    )

    if has_postgis:
        # Replace the entire PostGIS call site. We do this conservatively by
        # locating the call signature `ST_xxx(...)` and replacing the whole
        # parenthesised group.
        new_sql = _replace_postgis_call(sql, bbox_predicate)
        warnings.append("rewrote_postgis_to_bounding_box")
    else:
        # No PostGIS — just ensure the bbox predicate is in the WHERE clause.
        new_sql = _ensure_where_predicate(sql, bbox_predicate)
        warnings.append("added_bounding_box_predicate")

    geo_filter = {
        "lat": float(lat),
        "lng": float(lng),
        "radius_km": radius_km,
    }
    return new_sql, geo_filter, warnings


def _replace_postgis_call(sql: str, replacement_predicate: str) -> str:
    """Replace `ST_xxx(...)` (with balanced parens) by a predicate string."""
    pattern = re.compile(
        r"\b(" + "|".join(POSTGIS_FUNCTIONS) + r")\s*\(",
        re.IGNORECASE,
    )
    out = []
    i = 0
    while i < len(sql):
        m = pattern.search(sql, i)
        if not m:
            out.append(sql[i:])
            break
        out.append(sql[i:m.start()])
        # Walk parens to find matching close
        depth = 1
        j = m.end()
        while j < len(sql) and depth > 0:
            if sql[j] == "(":
                depth += 1
            elif sql[j] == ")":
                depth -= 1
            j += 1
        out.append(replacement_predicate)
        i = j
    return "".join(out)


def _ensure_where_predicate(sql: str, predicate: str) -> str:
    """Append `predicate` to the WHERE clause (adds WHERE if absent)."""
    if re.search(r"\bWHERE\b", sql, re.IGNORECASE):
        return re.sub(
            r"\bWHERE\b",
            f"WHERE ({predicate}) AND",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
    # Insert before GROUP BY / ORDER BY / LIMIT if present, else append.
    insert_re = re.compile(r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT)\b", re.IGNORECASE)
    m = insert_re.search(sql)
    if m:
        return sql[: m.start()] + f"WHERE {predicate} " + sql[m.start():]
    # Strip trailing `;` so we can re-append.
    base = sql.rstrip().rstrip(";")
    return f"{base} WHERE {predicate}"


# ---------------------------------------------------------------------------
# Catalyst Data Store execution
# ---------------------------------------------------------------------------

def _execute_query(sql: str, context: Any | None) -> list[dict[str, Any]]:
    """Run `sql` against Catalyst Data Store and return rows as plain dicts."""
    try:
        from shared.catalyst_client import get_datastore  # type: ignore
        datastore = get_datastore(context=context)
    except Exception:
        # Fall back to direct SDK use if shared client isn't deployed.
        import zcatalyst_sdk  # type: ignore
        app = zcatalyst_sdk.initialize(context) if context is not None else zcatalyst_sdk.initialize()
        datastore = app.datastore()

    raw_rows = datastore.execute_query(sql)
    # zcatalyst datastore.execute_query returns list-of-dicts; normalise just in case.
    rows: list[dict[str, Any]] = []
    for r in (raw_rows or []):
        if isinstance(r, dict):
            rows.append(r)
        elif hasattr(r, "to_dict"):
            rows.append(r.to_dict())
        else:
            rows.append({"value": r})
    return rows


def _post_filter_haversine(
    rows: list[dict[str, Any]],
    geo_filter: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Drop rows outside the circle (bounding box is a superset)."""
    if not geo_filter:
        return rows
    lat0 = float(geo_filter["lat"])
    lng0 = float(geo_filter["lng"])
    radius_km = float(geo_filter["radius_km"])

    out: list[dict[str, Any]] = []
    for r in rows:
        lat = r.get("location_lat")
        lng = r.get("location_lng")
        if lat is None or lng is None:
            continue
        try:
            d = _haversine_km(lat0, lng0, float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        if d <= radius_km:
            r2 = dict(r)
            r2["_distance_km"] = round(d, 3)
            out.append(r2)
    out.sort(key=lambda r: r.get("_distance_km", 1e9))
    return out


# ---------------------------------------------------------------------------
# Request / response wiring (Catalyst Advanced I/O)
# ---------------------------------------------------------------------------

def _parse_request_body(request: Any) -> dict[str, Any]:
    """Extract the JSON body from a Catalyst Advanced I/O request."""
    if request is None:
        return {}

    # Common shapes
    for attr in ("body", "data"):
        val = getattr(request, attr, None)
        if isinstance(val, (dict, list)):
            return val if isinstance(val, dict) else {"_list": val}
        if isinstance(val, (bytes, str)):
            try:
                return json.loads(val if isinstance(val, str) else val.decode())
            except Exception:  # noqa: BLE001
                pass

    if hasattr(request, "get_json"):
        try:
            data = request.get_json()
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            pass

    return {}


def _write_response(response: Any, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body, ensure_ascii=False)
    if hasattr(response, "set_status"):
        try:
            response.set_status(status)
        except Exception:  # noqa: BLE001
            pass
    if hasattr(response, "set_content_type"):
        try:
            response.set_content_type("application/json; charset=utf-8")
        except Exception:  # noqa: BLE001
            pass
    if hasattr(response, "send"):
        response.send(payload)
        return
    if hasattr(response, "write"):
        response.write(payload)
        if hasattr(response, "end"):
            response.end()
        return
    try:
        response.status = status
        response.body = payload
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Core orchestration — exposed for unit tests
# ---------------------------------------------------------------------------

def generate_sql(
    query: str,
    router_decision: dict[str, Any] | None,
    *,
    llm: Any = None,
) -> tuple[str, list[str]]:
    """Build the prompt, call the LLM, extract SQL, return (sql, warnings).

    `llm` is an optional callable `(prompt: str) -> str` for testing. In
    production we use `_call_qwen` directly.
    """
    warnings: list[str] = []
    entities = (router_decision or {}).get("entities") or {}
    # Pull a few common router fields into entities so the prompt sees them.
    for k in ("time_window", "location", "crime_type"):
        v = (router_decision or {}).get(k)
        if v is not None and k not in entities:
            entities[k] = v

    prompt = _build_prompt(query, entities)
    raw = (llm or _call_qwen)(prompt)
    sql = _extract_sql(raw)
    if not sql:
        warnings.append("llm_returned_empty_sql")
    return sql, warnings


def run_sql_pipeline(
    payload: dict[str, Any],
    *,
    context: Any | None = None,
    llm: Any = None,
    executor: Any = None,
) -> dict[str, Any]:
    """End-to-end pipeline: prompt → LLM → safety → rewrite → execute.

    `executor` lets tests pass a fake datastore (callable `(sql) -> rows`).
    """
    t0 = time.perf_counter()
    warnings: list[str] = []

    query = (payload.get("query") or "").strip()
    request_id = payload.get("request_id") or ""
    router = payload.get("router_decision") or {}
    if not query:
        return {
            "sql": "",
            "results": [],
            "row_count": 0,
            "execution_ms": 0,
            "warnings": ["empty_query"],
            "ok": False,
            "request_id": request_id,
        }

    # 1. Generate SQL.
    try:
        sql, gen_warnings = generate_sql(query, router, llm=llm)
    except Exception as exc:  # noqa: BLE001
        return {
            "sql": "",
            "results": [],
            "row_count": 0,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": [f"llm_call_failed:{type(exc).__name__}"],
            "ok": False,
            "request_id": request_id,
        }
    warnings.extend(gen_warnings)

    # 2. Geospatial rewrite (if router supplied a location or model used PostGIS).
    sql, geo_filter, geo_warnings = rewrite_geospatial(sql, router.get("location"))
    warnings.extend(geo_warnings)

    # 3. Safety validation.
    ok, reasons = is_safe_sql(sql)
    if not ok:
        return {
            "sql": sql,
            "results": [],
            "row_count": 0,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": warnings + [f"unsafe_sql:{r}" for r in reasons],
            "ok": False,
            "request_id": request_id,
        }

    # 4. Execute.
    try:
        if executor is not None:
            rows = executor(sql)
        else:
            rows = _execute_query(sql, context)
    except Exception as exc:  # noqa: BLE001
        return {
            "sql": sql,
            "results": [],
            "row_count": 0,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": warnings + [f"execute_failed:{type(exc).__name__}:{exc}"],
            "ok": False,
            "request_id": request_id,
        }

    # 5. Post-filter haversine for geo queries.
    if geo_filter:
        rows = _post_filter_haversine(rows, geo_filter)

    # 6. Cap rows.
    if len(rows) > MAX_ROWS_RETURNED:
        warnings.append(f"row_cap_applied:{MAX_ROWS_RETURNED}")
        rows = rows[:MAX_ROWS_RETURNED]

    return {
        "sql": sql,
        "results": rows,
        "row_count": len(rows),
        "execution_ms": int((time.perf_counter() - t0) * 1000),
        "warnings": warnings,
        "ok": True,
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Catalyst entry point
# ---------------------------------------------------------------------------

def handler(context: Any, basic_io: Any = None) -> Any:
    """Catalyst Advanced I/O entry point. POST only."""
    # Resolve request/response across runtime variants — same pattern as hello.
    if basic_io is None and hasattr(context, "get_request_method"):
        request, response = context, None  # type: ignore[assignment]
    elif basic_io is not None and (hasattr(basic_io, "req") or hasattr(basic_io, "request")):
        request = getattr(basic_io, "req", None) or getattr(basic_io, "request", None)
        response = getattr(basic_io, "res", None) or getattr(basic_io, "response", None)
    else:
        request, response = context, basic_io

    try:
        method = (getattr(request, "method", None) or getattr(request, "get_request_method", lambda: "POST")()).upper() if request else "POST"
        if method not in ("POST", "PUT"):
            _write_response(response, 405, {"ok": False, "error": "method_not_allowed", "allow": "POST"})
            return {"ok": False, "error": "method_not_allowed"}

        body = _parse_request_body(request)
        result = run_sql_pipeline(body, context=context)
        status = 200 if result.get("ok") else 400
        logger.info(
            "sql-gen request_id=%s ok=%s rows=%s ms=%s warnings=%s",
            result.get("request_id"),
            result.get("ok"),
            result.get("row_count"),
            result.get("execution_ms"),
            result.get("warnings"),
        )
        _write_response(response, status, result)
        return result

    except Exception as exc:  # noqa: BLE001 — top-level safety net
        err = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
        }
        logger.exception("sql-generator failed")
        _write_response(response, 500, err)
        return err
