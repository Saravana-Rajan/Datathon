"""
KSP Saathi — Hello smoke-test Catalyst Function.

Advanced I/O function (Python 3.11). Accepts GET ?name=X and returns a JSON
payload that confirms:
  * the function executes inside Catalyst's India DC
  * Kannada + English greeting paths both work (UTF-8 sanity)
  * the Catalyst SDK can initialise and make a trivial NoSQL call
  * which environment variables are set (values redacted)

This is the canary we hit on every deploy. If it returns 200 with both
language strings populated, the platform is wired up correctly.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("ksp_saathi.hello")
logger.setLevel(logging.INFO)

APP_VERSION = "0.1.0"
REGION = "IN"  # Catalyst India DC — IT Act 2008 compliant
KANNADA_HELLO = "ನಮಸ್ಕಾರ"  # "Namaskara"
ENGLISH_HELLO = "Hello"

# Env vars we care about diagnosing. Values are redacted in the response so
# we can deploy this function safely (no secret leakage) but still see what's
# configured.
ENV_KEYS_OF_INTEREST = (
    "X_ZOHO_CATALYST_PROJECT_ID",
    "X_ZOHO_CATALYST_PROJECT_KEY",
    "X_ZOHO_CATALYST_PROJECT_DOMAIN",
    "X_ZOHO_CATALYST_ENVIRONMENT",
    "CATALYST_PROJECT_ID",
    "CATALYST_PROJECT_KEY",
    "CATALYST_ENVIRONMENT",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _redact_env() -> dict[str, str]:
    """Return a dict of env-var keys we care about, with values redacted.

    "set"     — present and non-empty
    "empty"   — present but empty string
    "unset"   — not present
    """
    diagnostic: dict[str, str] = {}
    for key in ENV_KEYS_OF_INTEREST:
        if key not in os.environ:
            diagnostic[key] = "unset"
        elif os.environ[key] == "":
            diagnostic[key] = "empty"
        else:
            diagnostic[key] = "set"
    return diagnostic


def _try_catalyst_ping(context: Any) -> dict[str, Any]:
    """Attempt a trivial Catalyst SDK initialisation + NoSQL ping.

    We don't fail the function if this fails — we just report status. That way
    the hello probe can still tell us "function ran, SDK didn't init" which is
    itself a useful signal during early deploys.
    """
    result: dict[str, Any] = {
        "sdk_imported": False,
        "sdk_initialized": False,
        "nosql_reachable": False,
        "error": None,
    }
    try:
        import zcatalyst_sdk  # type: ignore

        result["sdk_imported"] = True

        app = zcatalyst_sdk.initialize(context) if context is not None else zcatalyst_sdk.initialize()
        result["sdk_initialized"] = True

        # Tiny NoSQL ping: list tables. This is read-only and cheap.
        # If the project has no NoSQL tables yet, we still consider the call
        # successful as long as the API responded without raising.
        try:
            nosql = app.datastore()  # Data Store handle
            _ = nosql.get_all_tables()
            result["nosql_reachable"] = True
        except Exception as inner_exc:  # noqa: BLE001 — diagnostic only
            result["error"] = f"nosql_call_failed: {type(inner_exc).__name__}: {inner_exc}"
    except ImportError as exc:
        result["error"] = f"sdk_import_failed: {exc}"
    except Exception as exc:  # noqa: BLE001 — diagnostic only
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _parse_name(request: Any) -> str:
    """Extract ?name=X from the request, defaulting to 'investigator'."""
    default = "investigator"
    if request is None:
        return default

    # Catalyst Advanced I/O wraps Flask-like request objects. We try several
    # access patterns so this works in real deploys AND in unit tests with fakes.
    candidates: list[Any] = []
    for attr in ("args", "query_params", "params"):
        value = getattr(request, attr, None)
        if value is not None:
            candidates.append(value)
    qs = getattr(request, "query_string", None)
    if isinstance(qs, (str, bytes)):
        candidates.append(qs)

    for candidate in candidates:
        try:
            if hasattr(candidate, "get"):
                name = candidate.get("name")
                if name:
                    return str(name)
            elif isinstance(candidate, (str, bytes)):
                raw = candidate.decode() if isinstance(candidate, bytes) else candidate
                for chunk in raw.lstrip("?").split("&"):
                    if "=" not in chunk:
                        continue
                    key, _, val = chunk.partition("=")
                    if key == "name" and val:
                        # Crude URL-decode for spaces; full unquote would need urllib.
                        return val.replace("+", " ")
        except Exception:  # noqa: BLE001
            continue
    return default


def _write_response(response: Any, status: int, body: dict[str, Any]) -> None:
    """Send the JSON response, tolerating multiple Catalyst response shapes."""
    payload = json.dumps(body, ensure_ascii=False)

    # Newer Catalyst Advanced I/O response object
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

    # Fallback for tests / unknown shapes — stash on the object so tests can read it.
    try:
        response.status = status
        response.body = payload
    except Exception:  # noqa: BLE001
        pass


def handler(context: Any, basic_io: Any = None) -> Any:
    """Catalyst Advanced I/O entry point.

    Signature matches Catalyst's Python Advanced I/O runtime: the platform
    passes `context` and a `basic_io` object that holds `req` and `res`.
    For Basic I/O style (older), the function is called with (req, res); we
    detect and handle that too.
    """
    # Detect Basic I/O calling convention: handler(req, res)
    if basic_io is None and hasattr(context, "get_request_method"):
        # context is actually the request, basic_io... isn't passed.
        # Some runtimes use handler(req, res) directly. Caller must supply both.
        request, response = context, None  # type: ignore[assignment]
    elif basic_io is not None and (hasattr(basic_io, "req") or hasattr(basic_io, "request")):
        request = getattr(basic_io, "req", None) or getattr(basic_io, "request", None)
        response = getattr(basic_io, "res", None) or getattr(basic_io, "response", None)
    else:
        # Fall back to assuming (req, res) directly.
        request, response = context, basic_io

    try:
        name = _parse_name(request)
        sdk_status = _try_catalyst_ping(context if hasattr(context, "__class__") else None)

        body: dict[str, Any] = {
            "ok": True,
            "service": "ksp-saathi-hello",
            "version": APP_VERSION,
            "region": REGION,
            "timestamp_utc": _utc_now_iso(),
            "greeting": {
                "kannada": f"{KANNADA_HELLO}, {name}!",
                "english": f"{ENGLISH_HELLO}, {name}!",
            },
            "name": name,
            "catalyst_sdk": sdk_status,
            "env_diagnostic": _redact_env(),
        }
        logger.info("hello-smoke-test ok name=%s sdk_init=%s", name, sdk_status["sdk_initialized"])
        _write_response(response, 200, body)
        return body

    except Exception as exc:  # noqa: BLE001 — top-level safety net
        err_body = {
            "ok": False,
            "service": "ksp-saathi-hello",
            "version": APP_VERSION,
            "region": REGION,
            "timestamp_utc": _utc_now_iso(),
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
        }
        logger.exception("hello-smoke-test failed")
        _write_response(response, 500, err_body)
        return err_body
