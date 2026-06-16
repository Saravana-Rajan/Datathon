"""Catalyst SDK wrapper for KSP Saathi.

Centralises access to the four Catalyst services the backend depends on:
    - Data Store (relational — FIRs, stations, accused)
    - NoSQL      (audit log, session state)
    - Cache      (5-min TTL on hot query results)
    - Stratus    (PDF exports, uploaded docs — optional helpers)

The zcatalyst-sdk-python package auto-loads its config from CATALYST_*
env vars (or the catalyst.json sitting beside the function). Each
function process gets one Catalyst app instance, reused per request.

Audit logging is first-class: every chat turn must call `log_audit(...)`
exactly once. See design.md §5.8 and §11.3.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# QuickML LLM Serving endpoint configuration
# ---------------------------------------------------------------------------
# QuickML exposes an OpenAI-compatible /v1/chat/completions endpoint. The
# router uses Qwen 2.5 7B Instruct (fastest model on the platform); the
# synthesizer uses 14B Instruct. Endpoints + keys come from env vars set in
# the Catalyst Function configuration.
QUICKML_BASE_URL = os.getenv(
    "CATALYST_QUICKML_BASE_URL",
    "https://quickml.catalyst.zoho.in/v1",
)
QUICKML_API_KEY = os.getenv("CATALYST_QUICKML_API_KEY", "")
QUICKML_ROUTER_MODEL = os.getenv(
    "CATALYST_QUICKML_ROUTER_MODEL",
    "qwen2.5-7b-instruct",
)
QUICKML_SYNTH_MODEL = os.getenv(
    "CATALYST_QUICKML_SYNTH_MODEL",
    "qwen2.5-14b-instruct",
)


# ---------------------------------------------------------------------------
# Lazy SDK import — zcatalyst_sdk may not be vendored in every dev shell
# ---------------------------------------------------------------------------
try:
    import zcatalyst_sdk
    _CATALYST_AVAILABLE = True
except ImportError:  # pragma: no cover — surfaced at call time
    zcatalyst_sdk = None  # type: ignore[assignment]
    _CATALYST_AVAILABLE = False


# Configuration
AUDIT_TABLE = os.getenv("CATALYST_AUDIT_TABLE", "audit_log")
SESSION_TABLE = os.getenv("CATALYST_SESSION_TABLE", "session_state")


class CatalystClientError(RuntimeError):
    """Raised when Catalyst services are unavailable or misconfigured."""


def _require_sdk() -> None:
    if not _CATALYST_AVAILABLE:
        raise CatalystClientError(
            "zcatalyst-sdk is not installed. Add it to requirements.txt for this function."
        )


# ---------------------------------------------------------------------------
# QuickML LLM Serving — OpenAI-compatible chat completions
# ---------------------------------------------------------------------------

def quickml_chat(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 256,
    response_format: dict | None = None,
    timeout_s: float = 8.0,
) -> str:
    """Call Catalyst QuickML LLM Serving (OpenAI-compatible /chat/completions).

    Returns the raw assistant message string. The caller is responsible for
    JSON parsing + schema validation.

    Raises CatalystClientError on any non-2xx response, network failure, or
    malformed body — callers should catch this and either fall back to Gemini
    or return a safe default to the user.
    """
    chosen_model = model or QUICKML_ROUTER_MODEL
    if not QUICKML_API_KEY:
        raise CatalystClientError(
            "CATALYST_QUICKML_API_KEY not set — cannot call QuickML LLM serving."
        )

    payload: dict[str, Any] = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {QUICKML_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(
                f"{QUICKML_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise CatalystClientError(f"QuickML network error: {exc}") from exc

    if resp.status_code >= 400:
        raise CatalystClientError(
            f"QuickML HTTP {resp.status_code}: {resp.text[:200]}"
        )

    try:
        body = resp.json()
        return body["choices"][0]["message"]["content"]
    except (KeyError, ValueError, IndexError) as exc:
        raise CatalystClientError(f"QuickML malformed response: {exc}") from exc


# ---------------------------------------------------------------------------
# Singleton app handle
# ---------------------------------------------------------------------------

class _CatalystApp:
    _instance: "_CatalystApp | None" = None

    def __init__(self, context: Any | None = None) -> None:
        _require_sdk()
        # zcatalyst_sdk.initialize() pulls credentials from either the
        # passed-in function context (in Catalyst Functions runtime) or
        # from env vars / catalyst.json (in local dev).
        if context is not None:
            self._app = zcatalyst_sdk.initialize(context)
        else:
            self._app = zcatalyst_sdk.initialize()
        logger.info("Catalyst app initialized")

    @classmethod
    def instance(cls, context: Any | None = None) -> "_CatalystApp":
        if cls._instance is None:
            cls._instance = cls(context=context)
        return cls._instance

    @property
    def app(self) -> Any:
        return self._app


def init_app(context: Any | None = None) -> Any:
    """Initialise (once per process) and return the raw Catalyst app handle.

    Pass the Catalyst Function `context` argument on cold start so the
    SDK uses the runtime credentials. In local dev, leave it as None and
    the SDK reads catalyst.json + env vars.
    """
    return _CatalystApp.instance(context=context).app


# ---------------------------------------------------------------------------
# Service handles
# ---------------------------------------------------------------------------

def get_datastore(context: Any | None = None) -> Any:
    """Return the Catalyst Data Store handle.

    Use `.table(name)` on the returned object to access a specific table:
        ds = get_datastore()
        firs = ds.table("firs")
        rows = firs.get_paged_rows()
    """
    return init_app(context).datastore()


def get_nosql(context: Any | None = None) -> Any:
    """Return the Catalyst NoSQL handle.

    Use `.table(name)` to access a NoSQL table (audit_log, session_state).
    """
    return init_app(context).nosql()


def get_cache(context: Any | None = None) -> Any:
    """Return the Catalyst Cache handle. Default segment unless customised."""
    return init_app(context).cache()


def get_stratus(context: Any | None = None) -> Any:
    """Return the Catalyst Stratus (object storage) handle."""
    return init_app(context).stratus()


# ---------------------------------------------------------------------------
# Audit log — every chat turn writes one record here
# ---------------------------------------------------------------------------

def log_audit(
    user_id: str,
    role: str,
    query: str,
    intent: str,
    sql: str | None,
    response: str,
    latency_ms: int,
    *,
    language: str | None = None,
    cypher: str | None = None,
    sources: list[dict[str, Any]] | None = None,
    confidence: float | None = None,
    request_id: str | None = None,
    context: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Write one audit entry to Catalyst NoSQL and return the request_id.

    Required keys per design.md §11.3:
        ts, user_id, role, language, raw_query, intent, sql/cypher,
        sources, response, latency_ms, request_id.

    On failure we log a warning but never raise — audit failures must not
    break the user-facing query path. (A separate Catalyst Signal can
    reconcile from the function log if NoSQL is briefly unavailable.)
    """
    req_id = request_id or str(uuid.uuid4())
    record = {
        "request_id": req_id,
        "ts": int(time.time() * 1000),
        "user_id": user_id,
        "role": role,
        "language": language,
        "raw_query": query,
        "intent": intent,
        "sql": sql,
        "cypher": cypher,
        "sources": sources or [],
        "response": response,
        "latency_ms": latency_ms,
        "confidence": confidence,
        "user_flagged_as_wrong": False,
    }
    if extra:
        record.update(extra)

    try:
        nosql = get_nosql(context=context)
        table = nosql.table(AUDIT_TABLE)
        # zcatalyst_sdk NoSQL: insert_items takes a list of items
        table.insert_items([{"item": record}])
        logger.debug("audit logged request_id=%s", req_id)
    except Exception as exc:  # noqa: BLE001 — audit must not break query path
        logger.warning("audit log write failed (request_id=%s): %s", req_id, exc)

    return req_id


# ---------------------------------------------------------------------------
# Session state helpers (short-term conversation memory)
# ---------------------------------------------------------------------------

def get_session(session_id: str, *, context: Any | None = None) -> dict[str, Any] | None:
    """Fetch the last-N-turns conversation state for a session, or None."""
    try:
        nosql = get_nosql(context=context)
        table = nosql.table(SESSION_TABLE)
        result = table.get_item({"id": session_id})
        return result.get("item") if isinstance(result, dict) else result
    except Exception as exc:  # noqa: BLE001
        logger.warning("session fetch failed (session_id=%s): %s", session_id, exc)
        return None


def put_session(session_id: str, state: dict[str, Any], *, context: Any | None = None) -> None:
    """Upsert the conversation state for a session."""
    try:
        nosql = get_nosql(context=context)
        table = nosql.table(SESSION_TABLE)
        table.insert_items([{"item": {"id": session_id, **state}}])
    except Exception as exc:  # noqa: BLE001
        logger.warning("session write failed (session_id=%s): %s", session_id, exc)
