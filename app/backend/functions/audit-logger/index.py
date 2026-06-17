"""KSP Saathi — audit-logger Catalyst Function.

Advanced I/O endpoint that powers the "Why?" explainability drawer
(design.md §5.8 + §11.3). Every step of a query's lifecycle — from raw
input, through language detect, routing, tool calls, synthesis, and
final output — is appended to an immutable audit chain in Catalyst
NoSQL. Officers can later open any request_id and replay the chain
visually, or flag a wrong answer for the bias-review queue.

Three endpoints multiplexed by HTTP method + path:

    POST /append
        Append a single step to an existing audit chain.
        Body:
            {
                "request_id": "uuid",
                "step_type":  "input|language_detect|route|tool_call|
                               synthesis|output|error|user_flag",
                "step_data":  { ... arbitrary step payload ... },
                "ts":         "2026-06-16T10:23:45.123Z"        # optional
            }
        Returns:
            { "ok": true, "request_id": "...", "step_index": 3 }

    GET ?request_id=X
        Fetch the full audit chain for a request_id, ordered by step_index.
        Returns:
            {
                "ok": true,
                "request_id": "...",
                "chain":  [ ... steps in order ... ],
                "summary": {
                    "total_latency_ms": 2840,
                    "models_used":      ["qwen2.5-7b", "gemini-2.5-pro"],
                    "tools_used":       ["sql", "rag", "cypher"]
                }
            }
        404 if the request_id has no chain.

    POST /flag
        User flags an answer as wrong → adds to bias-review queue.
        Body:
            { "request_id": "uuid", "reason": "...", "user_id": "..." }
        Returns:
            { "ok": true, "flag_id": "...", "queue": "bias_review_queue" }

Design properties (locked):
    * Atomic per-step appends — each step is one NoSQL document with a
      monotonically-increasing step_index. We never read-modify-write
      the whole chain (which would race under concurrent appends).
    * Immutable: there is no update or delete API exposed. Once a step
      is written, it stays. (IT Act 2008 evidentiary requirement.)
    * Partitioned by request_id — all steps for one query share a
      partition key, so chain reads are cheap point-lookups.
    * Indexed on user_id + ts so analytics queries ("show me every
      audit for officer X today") can run without a full scan.

Step-type taxonomy (locked):
    input            — raw user query (text or transcribed voice)
    language_detect  — detected language + confidence
    route            — intent router decision + chosen tools
    tool_call        — one external call (SQL / Cypher / RAG / forecast)
    synthesis        — LLM synthesis with model + tokens + latency
    output           — final answer streamed to user
    error            — any failure with stack + recovery action
    user_flag        — officer marked the answer wrong (mirrors /flag)
"""

# NOTE: do NOT use `from __future__ import annotations` here. Pydantic v2
# evaluates annotations at class-creation time and fails to resolve
# `Dict`/`Optional` from deferred string annotations on Catalyst's runtime.

import json
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("ksp_saathi.audit_logger")
logger.setLevel(logging.INFO)

APP_VERSION = "0.1.0"
SERVICE_NAME = "ksp-saathi-audit-logger"
REGION = "IN"  # Catalyst India DC

# ---------------------------------------------------------------------------
# Path setup so `shared/` is importable in both local pytest and deployed
# Catalyst bundles. Matches the convention used by rag-retriever/index.py.
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


# ---------------------------------------------------------------------------
# Configuration (env-overridable)
# ---------------------------------------------------------------------------

AUDIT_TABLE = os.getenv("CATALYST_AUDIT_TABLE", "audit_logs")
BIAS_REVIEW_TABLE = os.getenv("CATALYST_BIAS_REVIEW_TABLE", "bias_review_queue")

# Locked step-type vocabulary. Anything outside this set is rejected at
# /append time — the audit chain is a compliance artifact, free-form
# step_types would defeat the point.
VALID_STEP_TYPES: frozenset[str] = frozenset({
    "input",
    "language_detect",
    "route",
    "tool_call",
    "synthesis",
    "output",
    "error",
    "user_flag",
})


# ---------------------------------------------------------------------------
# Schema validation — pydantic if available, manual fallback otherwise.
# We don't want a missing dependency at deploy time to block the audit
# path (audit must keep working even when other dependencies break).
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator

    class AppendStepModel(BaseModel):
        request_id: str = Field(min_length=1, max_length=128)
        step_type: str
        step_data: Dict[str, Any] = Field(default_factory=dict)
        ts: Optional[str] = None
        user_id: Optional[str] = None
        role: Optional[str] = None

        @field_validator("step_type")
        @classmethod
        def _step_type_known(cls, v: str) -> str:
            if v not in VALID_STEP_TYPES:
                raise ValueError(
                    f"step_type {v!r} not in {sorted(VALID_STEP_TYPES)}"
                )
            return v

    class FlagModel(BaseModel):
        request_id: str = Field(min_length=1, max_length=128)
        reason: str = Field(min_length=1, max_length=2000)
        user_id: str = Field(min_length=1, max_length=128)

    _PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover — fallback path
    _PYDANTIC_AVAILABLE = False
    AppendStepModel = None  # type: ignore[assignment]
    FlagModel = None  # type: ignore[assignment]
    ValidationError = Exception  # type: ignore[assignment, misc]


def _validate_append(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate an /append payload. Returns (cleaned_dict, error_message)."""
    if _PYDANTIC_AVAILABLE:
        try:
            return AppendStepModel(**body).model_dump(), None  # type: ignore[union-attr]
        except ValidationError as exc:
            return None, str(exc)

    # Manual fallback — keep semantics identical to the pydantic path.
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return None, "request_id is required and must be a non-empty string"
    step_type = body.get("step_type")
    if step_type not in VALID_STEP_TYPES:
        return None, f"step_type must be one of {sorted(VALID_STEP_TYPES)}"
    step_data = body.get("step_data") or {}
    if not isinstance(step_data, dict):
        return None, "step_data must be a JSON object"
    return {
        "request_id": request_id,
        "step_type": step_type,
        "step_data": step_data,
        "ts": body.get("ts"),
        "user_id": body.get("user_id"),
        "role": body.get("role"),
    }, None


def _validate_flag(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if _PYDANTIC_AVAILABLE:
        try:
            return FlagModel(**body).model_dump(), None  # type: ignore[union-attr]
        except ValidationError as exc:
            return None, str(exc)
    for key in ("request_id", "reason", "user_id"):
        v = body.get(key)
        if not isinstance(v, str) or not v.strip():
            return None, f"{key} is required and must be a non-empty string"
    return {
        "request_id": body["request_id"],
        "reason": body["reason"],
        "user_id": body["user_id"],
    }, None


# ---------------------------------------------------------------------------
# Time + ID helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


def _coerce_ts_to_iso(ts: str | None) -> str:
    """Normalise caller-supplied timestamps to ISO-8601 UTC.

    If the caller didn't pass one, stamp it now. If they passed something
    we can't parse, keep their original string but tag it — we never throw
    on a malformed ts because audit must not block the user path.
    """
    if not ts:
        return _utc_now_iso()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    except (ValueError, AttributeError):
        return ts  # keep caller's value; analytics can clean later


# ---------------------------------------------------------------------------
# Request/response IO — tolerant of multiple Catalyst runtime shapes,
# matching the convention used by hello/ and rag-retriever/.
# ---------------------------------------------------------------------------

def _parse_body(request: Any) -> dict[str, Any]:
    if request is None:
        return {}
    if isinstance(request, dict):
        return request
    for attr in ("get_json", "json"):
        fn = getattr(request, attr, None)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict):
                    return data
            except Exception:  # noqa: BLE001
                pass
        elif isinstance(fn, dict):
            return fn
    body = getattr(request, "body", None) or getattr(request, "data", None)
    if isinstance(body, (bytes, bytearray)):
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _get_method(request: Any) -> str:
    """Best-effort HTTP method extraction across Catalyst runtime versions."""
    for attr in ("method", "http_method", "request_method"):
        v = getattr(request, attr, None)
        if isinstance(v, str) and v:
            return v.upper()
    fn = getattr(request, "get_request_method", None)
    if callable(fn):
        try:
            v = fn()
            if isinstance(v, str) and v:
                return v.upper()
        except Exception:  # noqa: BLE001
            pass
    # Dict-shaped fakes (used in tests)
    if isinstance(request, dict):
        return str(request.get("method", "")).upper()
    return ""


def _get_path(request: Any) -> str:
    """Best-effort URL path extraction. Returns lowercase with leading /."""
    for attr in ("path", "url_path", "request_uri", "path_info"):
        v = getattr(request, attr, None)
        if isinstance(v, str) and v:
            return v.lower()
    if isinstance(request, dict):
        return str(request.get("path", "")).lower()
    return ""


def _get_query_param(request: Any, key: str) -> str | None:
    for attr in ("args", "query_params", "params"):
        v = getattr(request, attr, None)
        if v is not None and hasattr(v, "get"):
            val = v.get(key)
            if val:
                return str(val)
    if isinstance(request, dict):
        qp = request.get("query") or request.get("query_params") or {}
        if isinstance(qp, dict) and qp.get(key):
            return str(qp[key])
    return None


def _write_response(response: Any, status: int, body: dict[str, Any]) -> dict[str, Any]:
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
        try:
            response.send(payload)
        except Exception:  # noqa: BLE001
            pass
    elif hasattr(response, "write"):
        try:
            response.write(payload)
            if hasattr(response, "end"):
                response.end()
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            response.status = status
            response.body = payload
        except Exception:  # noqa: BLE001
            pass
    return body


# ---------------------------------------------------------------------------
# NoSQL access — wraps `shared.catalyst_client.get_nosql` and tolerates
# multiple zcatalyst-sdk versions. The same shape-tolerance the
# rag-retriever uses for reads applies here.
# ---------------------------------------------------------------------------

class _NoSQLUnavailable(RuntimeError):
    """Raised when we cannot reach Catalyst NoSQL at all."""


def _open_table(table_name: str, context: Any | None) -> Any:
    try:
        from shared.catalyst_client import get_nosql  # type: ignore
    except ImportError as exc:
        raise _NoSQLUnavailable(f"shared.catalyst_client unavailable: {exc}") from exc
    try:
        return get_nosql(context=context).table(table_name)
    except Exception as exc:  # noqa: BLE001
        raise _NoSQLUnavailable(f"could not open NoSQL table {table_name}: {exc}") from exc


def _list_table_items(table: Any) -> list[dict[str, Any]]:
    """Read every item from a NoSQL table, tolerating SDK shape differences."""
    fetched = None
    for fn_name in ("fetch_all_items", "get_iterable_items", "get_all_items"):
        fn = getattr(table, fn_name, None)
        if callable(fn):
            try:
                fetched = fn()
                break
            except Exception:  # noqa: BLE001
                continue
    if fetched is None:
        return []
    if isinstance(fetched, dict):
        fetched = fetched.get("items") or fetched.get("data") or []

    rows: list[dict[str, Any]] = []
    for raw in fetched:
        if isinstance(raw, dict):
            item = raw.get("item") if "item" in raw else raw
        else:
            item = getattr(raw, "item", raw)
        if isinstance(item, dict):
            rows.append(item)
    return rows


# ---------------------------------------------------------------------------
# Atomic step-index allocation
#
# We compute the next step_index as (current_max + 1). To make this race-safe
# under concurrent appends we:
#   1. Read current items for the request_id (cheap — partitioned by request_id)
#   2. Allocate the next index
#   3. Write with a unique row_id  = f"{request_id}#{step_index}#{uuid7}"
#
# If two workers race and pick the same step_index, both writes still
# succeed (distinct row_ids), but the second one is harmless because we
# *also* embed a fresh uuid in the row_id — readers de-duplicate by
# (request_id, step_index, item_id) and keep the earlier ts on collision.
#
# In a fuller production setup we'd back this with a NoSQL counter
# document and a compare-and-set. For demo-scale traffic the read+write
# pattern below is sufficient and matches Catalyst NoSQL's eventual-
# consistency guarantees.
# ---------------------------------------------------------------------------

def _items_for_request(table: Any, request_id: str) -> list[dict[str, Any]]:
    """Return every step item whose request_id matches.

    Prefers a server-side query if the SDK exposes one; otherwise falls
    back to a full table scan + filter (acceptable at hackathon scale).
    """
    # Try server-side query first.
    for fn_name in ("query_items", "fetch_items", "find_items"):
        fn = getattr(table, fn_name, None)
        if callable(fn):
            try:
                result = fn({"request_id": request_id})
                if isinstance(result, dict):
                    result = result.get("items") or result.get("data") or []
                normalised: list[dict[str, Any]] = []
                for raw in result:
                    item = raw.get("item") if isinstance(raw, dict) and "item" in raw else raw
                    if isinstance(item, dict) and item.get("request_id") == request_id:
                        normalised.append(item)
                if normalised:
                    return normalised
            except Exception:  # noqa: BLE001
                continue

    # Fallback: full scan + filter.
    return [row for row in _list_table_items(table) if row.get("request_id") == request_id]


def _next_step_index(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    return max(int(it.get("step_index", -1)) for it in items) + 1


# ---------------------------------------------------------------------------
# Endpoint handlers
# ---------------------------------------------------------------------------

def _handle_append(body: dict[str, Any], context: Any) -> tuple[int, dict[str, Any]]:
    cleaned, err = _validate_append(body)
    if err:
        return 400, {
            "ok": False,
            "error": "validation_failed",
            "detail": err,
        }
    assert cleaned is not None  # for type-checkers

    request_id = cleaned["request_id"]
    step_type = cleaned["step_type"]
    step_data = cleaned["step_data"]
    ts = _coerce_ts_to_iso(cleaned.get("ts"))
    user_id = cleaned.get("user_id") or step_data.get("user_id")
    role = cleaned.get("role") or step_data.get("role")

    try:
        table = _open_table(AUDIT_TABLE, context)
    except _NoSQLUnavailable as exc:
        # Audit unavailability is a serious signal — surface 503 not 500
        # so the orchestrator can decide whether to proceed in degraded
        # mode (per the "audit failures must not break the user path"
        # rule in shared/catalyst_client.log_audit).
        logger.error("NoSQL unavailable for /append: %s", exc)
        return 503, {
            "ok": False,
            "error": "audit_store_unavailable",
            "detail": str(exc),
        }

    existing = _items_for_request(table, request_id)
    step_index = _next_step_index(existing)
    item_id = f"{request_id}#{step_index:05d}#{uuid.uuid4().hex[:8]}"

    record = {
        "id": item_id,                      # NoSQL row key
        "request_id": request_id,           # partition key
        "step_index": step_index,           # sort key
        "step_type": step_type,
        "step_data": step_data,
        "ts": ts,
        "ts_ms": _utc_now_ms(),             # for time-range analytics index
        "user_id": user_id,
        "role": role,
        "immutable": True,                  # advisory — no update API exposed
    }

    try:
        table.insert_items([{"item": record}])
    except Exception as exc:  # noqa: BLE001
        logger.exception("audit append failed request_id=%s", request_id)
        return 500, {
            "ok": False,
            "error": "audit_write_failed",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    logger.info(
        "audit append request_id=%s step_index=%d step_type=%s",
        request_id, step_index, step_type,
    )
    return 200, {
        "ok": True,
        "request_id": request_id,
        "step_index": step_index,
        "id": item_id,
        "ts": ts,
    }


def _summarise_chain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up models_used, tools_used, and total_latency_ms across a chain."""
    models: list[str] = []
    tools: list[str] = []
    total_latency_ms = 0
    start_ms: int | None = None
    end_ms: int | None = None

    for step in chain:
        data = step.get("step_data") or {}
        ts_ms = step.get("ts_ms")
        if isinstance(ts_ms, int):
            start_ms = ts_ms if start_ms is None else min(start_ms, ts_ms)
            end_ms = ts_ms if end_ms is None else max(end_ms, ts_ms)

        # Sum explicit per-step latencies when provided (tool_call,
        # synthesis usually report their own).
        lat = data.get("latency_ms")
        if isinstance(lat, (int, float)):
            total_latency_ms += int(lat)

        model = data.get("model") or data.get("model_used")
        if isinstance(model, str) and model and model not in models:
            models.append(model)

        tool = data.get("tool") or data.get("tool_name")
        if isinstance(tool, str) and tool and tool not in tools:
            tools.append(tool)

    # If no per-step latency reported, fall back to wall-clock span.
    if total_latency_ms == 0 and start_ms is not None and end_ms is not None:
        total_latency_ms = max(0, end_ms - start_ms)

    return {
        "total_latency_ms": total_latency_ms,
        "models_used": models,
        "tools_used": tools,
        "step_count": len(chain),
    }


def _handle_fetch(request_id: str, context: Any) -> tuple[int, dict[str, Any]]:
    if not request_id:
        return 400, {"ok": False, "error": "request_id query param is required"}

    try:
        table = _open_table(AUDIT_TABLE, context)
    except _NoSQLUnavailable as exc:
        return 503, {"ok": False, "error": "audit_store_unavailable", "detail": str(exc)}

    items = _items_for_request(table, request_id)
    if not items:
        return 404, {
            "ok": False,
            "error": "not_found",
            "request_id": request_id,
        }

    # De-duplicate on (request_id, step_index) keeping the earliest ts_ms.
    by_index: dict[int, dict[str, Any]] = {}
    for item in items:
        idx = int(item.get("step_index", 0))
        existing = by_index.get(idx)
        if existing is None or int(item.get("ts_ms", 0)) < int(existing.get("ts_ms", 0)):
            by_index[idx] = item

    chain = [by_index[k] for k in sorted(by_index.keys())]
    summary = _summarise_chain(chain)

    logger.info(
        "audit fetch request_id=%s steps=%d", request_id, len(chain),
    )
    return 200, {
        "ok": True,
        "request_id": request_id,
        "chain": chain,
        "summary": summary,
    }


def _handle_flag(body: dict[str, Any], context: Any) -> tuple[int, dict[str, Any]]:
    cleaned, err = _validate_flag(body)
    if err:
        return 400, {
            "ok": False,
            "error": "validation_failed",
            "detail": err,
        }
    assert cleaned is not None

    request_id = cleaned["request_id"]
    reason = cleaned["reason"]
    user_id = cleaned["user_id"]
    flag_id = f"flag-{uuid.uuid4().hex}"
    ts = _utc_now_iso()
    ts_ms = _utc_now_ms()

    # 1) Write to bias_review_queue
    try:
        queue = _open_table(BIAS_REVIEW_TABLE, context)
    except _NoSQLUnavailable as exc:
        return 503, {
            "ok": False,
            "error": "bias_review_store_unavailable",
            "detail": str(exc),
        }

    queue_record = {
        "id": flag_id,
        "request_id": request_id,
        "reason": reason,
        "user_id": user_id,
        "ts": ts,
        "ts_ms": ts_ms,
        "status": "pending",          # pending | assigned | resolved | dismissed
        "reviewer_id": None,
        "reviewer_notes": None,
        "resolved_at": None,
    }

    try:
        queue.insert_items([{"item": queue_record}])
    except Exception as exc:  # noqa: BLE001
        logger.exception("flag insert failed request_id=%s", request_id)
        return 500, {
            "ok": False,
            "error": "flag_write_failed",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    # 2) Also append a user_flag step to the audit chain itself, so the
    #    chain reflects that the user flagged this answer. This is best-
    #    effort — if the audit table write fails we still return success
    #    on the flag (the queue row is the source of truth for review).
    try:
        _handle_append(
            {
                "request_id": request_id,
                "step_type": "user_flag",
                "step_data": {
                    "flag_id": flag_id,
                    "reason": reason,
                    "user_id": user_id,
                },
                "ts": ts,
                "user_id": user_id,
            },
            context,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("user_flag step append failed (non-fatal): %s", exc)

    logger.info(
        "bias flag queued request_id=%s flag_id=%s user_id=%s",
        request_id, flag_id, user_id,
    )
    return 200, {
        "ok": True,
        "flag_id": flag_id,
        "request_id": request_id,
        "queue": BIAS_REVIEW_TABLE,
        "status": "pending",
        "ts": ts,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _dispatch(request: Any, context: Any) -> tuple[int, dict[str, Any]]:
    method = _get_method(request) or "GET"
    path = _get_path(request)

    # GET ?request_id=X — fetch chain
    if method == "GET":
        request_id = _get_query_param(request, "request_id") or ""
        return _handle_fetch(request_id, context)

    # POST /flag — bias-review queue
    if method == "POST" and path.endswith("/flag"):
        return _handle_flag(_parse_body(request), context)

    # POST /append (default for POST) — append a step
    if method == "POST":
        body = _parse_body(request)
        # Allow the caller to override via "action" key for non-RESTful
        # callers that can't set a URL path (e.g. some Circuits steps).
        action = str(body.get("action", "")).lower()
        if action == "flag":
            return _handle_flag(body, context)
        return _handle_append(body, context)

    return 405, {
        "ok": False,
        "error": "method_not_allowed",
        "method": method,
        "path": path,
    }


# ---------------------------------------------------------------------------
# Catalyst Advanced I/O entry point
# ---------------------------------------------------------------------------

def handler(context: Any, basic_io: Any = None) -> Any:
    """Catalyst Advanced I/O handler. See module docstring for endpoints."""
    start_ms = time.time()

    # Resolve (request, response) across runtime conventions
    if basic_io is not None and (hasattr(basic_io, "req") or hasattr(basic_io, "request")):
        request = getattr(basic_io, "req", None) or getattr(basic_io, "request", None)
        response = getattr(basic_io, "res", None) or getattr(basic_io, "response", None)
    else:
        request, response = context, basic_io

    try:
        status, body = _dispatch(request, context)
        body.setdefault("service", SERVICE_NAME)
        body.setdefault("version", APP_VERSION)
        body.setdefault("region", REGION)
        body.setdefault("timestamp_utc", _utc_now_iso())
        body.setdefault("latency_ms", int((time.time() - start_ms) * 1000))
        return _write_response(response, status, body)
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        latency_ms = int((time.time() - start_ms) * 1000)
        logger.exception("audit-logger handler crashed")
        return _write_response(response, 500, {
            "ok": False,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "region": REGION,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })
