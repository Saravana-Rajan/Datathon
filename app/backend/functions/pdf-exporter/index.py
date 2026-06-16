"""KSP Saathi — PDF exporter Catalyst Function.

Advanced I/O endpoint that produces a case-file-quality PDF of an officer's
conversation with KSP Saathi. Implements feature 5.4 of design.md:

    "Catalyst SmartBrowz generates branded PDF. Includes: chat transcript,
     embedded map screenshot, embedded graph, audit trail."

Request shape (POST):
    {
        "session_id": "sess_2026-06-16_abc123",
        "include_audit": true,
        "language": "kn" | "en" | "both"
    }

Response shape:
    {
        "ok": true,
        "pdf_url": "https://<stratus-bucket>.zohostratus.com/sessions/<id>.pdf",
        "size_bytes": 218443,
        "generated_at": "2026-06-16T11:42:07.123Z",
        "session_id": "sess_2026-06-16_abc123",
        "turns": 7,
        "latency_ms": 4321
    }

Pipeline (Catalyst-first; all data stays inside India DC):

    Catalyst NoSQL `sessions`  --->\\
                                   ---> Jinja2 render --> SmartBrowz HTML->PDF
    Catalyst NoSQL `audit_log` --->/                                 |
    Catalyst SmartBrowz         (static-Maps + graph-PNG screenshots) |
                                                                     v
                                                       Catalyst Stratus upload
                                                                     |
                                                                     v
                                                            signed URL returned

Why SmartBrowz for screenshots, not a custom map render: Catalyst has no Maps
service (design.md §6.3), and we have one external dependency on Google Maps.
SmartBrowz fetches the Google static Maps URL (which the frontend already
builds) and snapshots it server-side — so the PDF is reproducible from the
session_id alone, without any client interaction.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote_plus

logger = logging.getLogger("ksp_saathi.pdf_exporter")
logger.setLevel(logging.INFO)

APP_VERSION = "1.0.0"
SERVICE_NAME = "ksp-saathi-pdf-exporter"

# ---------------------------------------------------------------------------
# Path setup — make `shared/` importable both in pytest and in deployed bundles
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


# ---------------------------------------------------------------------------
# Configuration (env-overridable)
# ---------------------------------------------------------------------------

SESSIONS_TABLE = os.getenv("CATALYST_SESSIONS_TABLE", "sessions")
AUDIT_TABLE = os.getenv("CATALYST_AUDIT_TABLE", "audit_log")
STRATUS_BUCKET = os.getenv("CATALYST_STRATUS_BUCKET", "ksp-saathi-exports")
STRATUS_PREFIX = os.getenv("CATALYST_STRATUS_PREFIX", "sessions")
STRATUS_PUBLIC_BASE = os.getenv(
    "CATALYST_STRATUS_PUBLIC_BASE",
    f"https://{STRATUS_BUCKET}.zohostratus.com",
)
SIGNED_URL_TTL_S = int(os.getenv("CATALYST_STRATUS_SIGNED_TTL_S", "86400"))  # 24h

SMARTBROWZ_BASE = os.getenv(
    "CATALYST_SMARTBROWZ_BASE",
    "https://browser360.catalyst.zoho.in/v1",
)
SMARTBROWZ_API_KEY = os.getenv("CATALYST_SMARTBROWZ_API_KEY", "")
SMARTBROWZ_TIMEOUT_S = float(os.getenv("CATALYST_SMARTBROWZ_TIMEOUT_S", "20"))

GOOGLE_MAPS_STATIC_KEY = os.getenv("GOOGLE_MAPS_STATIC_KEY", "")
GOOGLE_MAPS_STATIC_BASE = "https://maps.googleapis.com/maps/api/staticmap"
GRAPH_RENDER_BASE = os.getenv("KSP_GRAPH_RENDER_BASE", "")  # internal graph PNG renderer

TEMPLATE_FILENAME = "template.html"


# ---------------------------------------------------------------------------
# Helpers — request / response across Catalyst Advanced I/O versions
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_body(request: Any) -> dict[str, Any]:
    """Tolerantly extract JSON body across Catalyst runtime shapes + dict fakes."""
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


def _write_response(response: Any, status: int, body: dict[str, Any]) -> dict[str, Any]:
    """Send JSON; tolerate multiple Catalyst response shapes. Returns body for tests."""
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
# Session + audit fetch
# ---------------------------------------------------------------------------

def _fetch_session(session_id: str, *, context: Any | None) -> dict[str, Any]:
    """Pull the session document from Catalyst NoSQL.

    Schema (per design.md §7.2):
        { id, officer_name, officer_role, jurisdiction, start_time,
          end_time, language_pref, turns: [ ... ] }

    Each turn carries:
        { request_id, timestamp, language, raw_query, query_en, query_kn,
          response, response_en, response_kn, intent, sources, latency_ms,
          viz_spec: { map?: {...}, graph?: {...} } }
    """
    try:
        from shared.catalyst_client import get_nosql  # type: ignore
    except ImportError as exc:
        logger.error("catalyst_client unavailable: %s", exc)
        return {}

    try:
        nosql = get_nosql(context=context)
        table = nosql.table(SESSIONS_TABLE)
        result = table.get_item({"id": session_id})
    except Exception as exc:  # noqa: BLE001
        logger.error("session fetch failed (id=%s): %s", session_id, exc)
        return {}

    if not result:
        return {}
    item = result.get("item") if isinstance(result, dict) else result
    return item if isinstance(item, dict) else {}


def _fetch_audit_chain(
    session_id: str,
    request_ids: Iterable[str],
    *,
    context: Any | None,
) -> list[dict[str, Any]]:
    """Pull all audit_log entries for the request_ids in this session.

    Walks each request_id individually — NoSQL get-by-key is the only
    semantically-safe API across SDK versions.
    """
    try:
        from shared.catalyst_client import get_nosql  # type: ignore
    except ImportError:
        return []

    try:
        nosql = get_nosql(context=context)
        table = nosql.table(AUDIT_TABLE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit table unavailable: %s", exc)
        return []

    entries: list[dict[str, Any]] = []
    for rid in request_ids:
        if not rid:
            continue
        try:
            row = table.get_item({"request_id": rid})
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit lookup miss (rid=%s): %s", rid, exc)
            continue
        if not row:
            continue
        item = row.get("item") if isinstance(row, dict) else row
        if isinstance(item, dict):
            ts = item.get("ts")
            if isinstance(ts, (int, float)):
                try:
                    item["ts_iso"] = datetime.fromtimestamp(
                        ts / 1000.0, tz=timezone.utc,
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:  # noqa: BLE001
                    item["ts_iso"] = str(ts)
            entries.append(item)
    entries.sort(key=lambda e: e.get("ts") or 0)
    return entries


# ---------------------------------------------------------------------------
# SmartBrowz client — screenshots and HTML→PDF
# ---------------------------------------------------------------------------

def _smartbrowz_post(path: str, payload: dict[str, Any], *, timeout: float | None = None) -> bytes:
    """POST to a SmartBrowz endpoint; return raw response bytes.

    Raises RuntimeError on transport/HTTP error. Keeps client-construction
    lazy so unit tests that monkeypatch this function never need httpx.
    """
    if not SMARTBROWZ_API_KEY:
        raise RuntimeError("CATALYST_SMARTBROWZ_API_KEY is not set")

    import httpx  # local import — keeps cold-start light when not needed

    url = f"{SMARTBROWZ_BASE.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {SMARTBROWZ_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout or SMARTBROWZ_TIMEOUT_S) as client:
        resp = client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"SmartBrowz {path} HTTP {resp.status_code}: {resp.text[:240]}")
    return resp.content


def _screenshot_url(url: str, *, viewport: tuple[int, int] = (720, 480)) -> bytes | None:
    """Use SmartBrowz to screenshot a static URL. Returns PNG bytes or None on failure."""
    try:
        return _smartbrowz_post(
            "screenshot",
            {
                "url": url,
                "format": "png",
                "viewport": {"width": viewport[0], "height": viewport[1]},
                "full_page": False,
                "wait_until": "networkidle",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("SmartBrowz screenshot failed for %s: %s", url, exc)
        return None


def _png_to_data_uri(png_bytes: bytes | None) -> str | None:
    if not png_bytes:
        return None
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Viz spec → static-image URL builders
# ---------------------------------------------------------------------------

def _build_static_maps_url(map_spec: dict[str, Any]) -> str | None:
    """Translate a viz_spec.map into a Google Static Maps URL.

    map_spec shape (from synthesizer):
        {
          "center": {"lat": 12.97, "lng": 77.59},
          "zoom":   13,
          "markers": [{"lat": 12.97, "lng": 77.59, "label": "A"}, ...],
          "heatmap": [{"lat": ..., "lng": ..., "weight": 0.8}, ...]   # optional
        }
    """
    if not map_spec or not GOOGLE_MAPS_STATIC_KEY:
        return None
    center = map_spec.get("center") or {}
    lat = center.get("lat")
    lng = center.get("lng")
    if lat is None or lng is None:
        return None
    zoom = int(map_spec.get("zoom") or 13)

    params = [
        f"center={lat},{lng}",
        f"zoom={zoom}",
        "size=720x480",
        "scale=2",
        "maptype=roadmap",
        f"key={quote_plus(GOOGLE_MAPS_STATIC_KEY)}",
    ]
    for m in (map_spec.get("markers") or [])[:24]:  # static-maps URL length limit
        mlat = m.get("lat"); mlng = m.get("lng")
        if mlat is None or mlng is None:
            continue
        label = quote_plus(str(m.get("label") or ""))[:1] or "A"
        params.append(f"markers=color:red%7Clabel:{label}%7C{mlat},{mlng}")
    return f"{GOOGLE_MAPS_STATIC_BASE}?{'&'.join(params)}"


def _build_graph_render_url(graph_spec: dict[str, Any], *, session_id: str, turn_idx: int) -> str | None:
    """Build a URL the internal graph renderer (or frontend /graph-png route) can hit.

    Falls back to None when no renderer is configured — caller will skip the
    graph screenshot for that turn rather than blowing up the export.
    """
    if not graph_spec or not GRAPH_RENDER_BASE:
        return None
    # The frontend already has a /graph/png?session=...&turn=... route that
    # renders the React-Flow graph to a static PNG using puppeteer. We just
    # ask SmartBrowz to screenshot it.
    return (
        f"{GRAPH_RENDER_BASE.rstrip('/')}/graph/png"
        f"?session={quote_plus(session_id)}&turn={turn_idx}"
    )


# ---------------------------------------------------------------------------
# Per-turn snapshot enrichment
# ---------------------------------------------------------------------------

def _enrich_turn_snapshots(turn: dict[str, Any], *, session_id: str, turn_idx: int) -> dict[str, Any]:
    """Add map_snapshot_data_uri / graph_snapshot_data_uri to a turn.

    Mutates and returns the same dict so the template can embed them inline.
    Failures are silent — the export still ships, just without that image.
    """
    viz = turn.get("viz_spec") or {}
    map_spec = viz.get("map") if isinstance(viz, dict) else None
    graph_spec = viz.get("graph") if isinstance(viz, dict) else None

    if map_spec:
        maps_url = _build_static_maps_url(map_spec)
        if maps_url:
            png = _screenshot_url(maps_url, viewport=(720, 480))
            turn["map_snapshot_data_uri"] = _png_to_data_uri(png)

    if graph_spec:
        graph_url = _build_graph_render_url(graph_spec, session_id=session_id, turn_idx=turn_idx)
        if graph_url:
            png = _screenshot_url(graph_url, viewport=(720, 480))
            turn["graph_snapshot_data_uri"] = _png_to_data_uri(png)

    return turn


# ---------------------------------------------------------------------------
# Jinja2 render
# ---------------------------------------------------------------------------

def _load_template_source() -> str:
    """Read template.html from disk (sibling of this index.py)."""
    path = os.path.join(_HERE, TEMPLATE_FILENAME)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def render_html(
    session: dict[str, Any],
    turns: list[dict[str, Any]],
    *,
    language: str,
    include_audit: bool,
    audit_entries: list[dict[str, Any]] | None = None,
    export_request_id: str | None = None,
    generated_at: str | None = None,
) -> str:
    """Render the case-file HTML. Exposed for unit-test inspection."""
    from jinja2 import Environment, BaseLoader, select_autoescape

    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    template = env.from_string(_load_template_source())

    language_label = {
        "kn": "ಕನ್ನಡ (Kannada)",
        "en": "English",
        "both": "English + ಕನ್ನಡ",
    }.get(language, language)

    return template.render(
        session=session,
        turns=turns,
        language=language,
        language_label=language_label,
        show_en=language in ("en", "both"),
        show_kn=language in ("kn", "both"),
        include_audit=include_audit,
        audit_entries=audit_entries or [],
        export_request_id=export_request_id or str(uuid.uuid4()),
        generated_at=generated_at or _utc_now_iso(),
    )


# ---------------------------------------------------------------------------
# HTML → PDF via SmartBrowz
# ---------------------------------------------------------------------------

def html_to_pdf(html: str) -> bytes:
    """Render HTML to PDF using Catalyst SmartBrowz.

    SmartBrowz exposes a `/pdf` endpoint that accepts a full HTML document.
    Returns the raw PDF bytes. Raises RuntimeError on transport/HTTP errors.
    """
    payload = {
        "html": html,
        "format": "A4",
        "print_background": True,
        "margin": {"top": "18mm", "bottom": "22mm", "left": "16mm", "right": "16mm"},
        "wait_until": "networkidle",
        "scale": 1.0,
    }
    return _smartbrowz_post("pdf", payload, timeout=SMARTBROWZ_TIMEOUT_S * 2)


# ---------------------------------------------------------------------------
# Stratus upload + signed URL
# ---------------------------------------------------------------------------

def upload_to_stratus(
    pdf_bytes: bytes,
    object_key: str,
    *,
    context: Any | None = None,
) -> str:
    """Upload PDF to Catalyst Stratus and return a signed URL.

    Falls back to a plain public-base URL if the SDK doesn't expose a signed-URL
    helper on this version. The bucket itself is private-by-default; the
    fallback is fine for hackathon-demo traffic but should be tightened with
    Catalyst's `generate_signed_url` when GA.
    """
    try:
        from shared.catalyst_client import get_stratus  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f"catalyst_client unavailable: {exc}") from exc

    stratus = get_stratus(context=context)
    bucket = None
    for fn_name in ("bucket", "get_bucket"):
        fn = getattr(stratus, fn_name, None)
        if callable(fn):
            try:
                bucket = fn(STRATUS_BUCKET)
                break
            except Exception:  # noqa: BLE001
                continue
    if bucket is None:
        raise RuntimeError(f"could not open Stratus bucket {STRATUS_BUCKET}")

    # Upload — try the common SDK shapes
    fp = io.BytesIO(pdf_bytes)
    uploaded = False
    for fn_name in ("put_object", "upload_object", "upload_file", "put"):
        fn = getattr(bucket, fn_name, None)
        if callable(fn):
            try:
                # Most SDK variants take (key, file_obj, content_type=...)
                fp.seek(0)
                fn(object_key, fp, content_type="application/pdf")
                uploaded = True
                break
            except TypeError:
                try:
                    fp.seek(0)
                    fn(key=object_key, body=fp, content_type="application/pdf")
                    uploaded = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.debug("Stratus %s failed: %s — trying next", fn_name, exc)
                continue
    if not uploaded:
        raise RuntimeError("no Stratus upload method worked")

    # Generate signed URL — best-effort across SDK shapes
    signed_url: str | None = None
    for fn_name in ("generate_signed_url", "get_signed_url", "generate_pre_signed_url"):
        fn = getattr(bucket, fn_name, None)
        if callable(fn):
            try:
                signed_url = fn(object_key, expires_in=SIGNED_URL_TTL_S)
                break
            except TypeError:
                try:
                    signed_url = fn(object_key)
                    break
                except Exception:  # noqa: BLE001
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.debug("Stratus %s failed: %s — falling back to public URL", fn_name, exc)
                continue

    if not signed_url:
        signed_url = f"{STRATUS_PUBLIC_BASE.rstrip('/')}/{object_key}"

    return signed_url


# ---------------------------------------------------------------------------
# Core export pipeline — exposed for testing
# ---------------------------------------------------------------------------

def export_session_pdf(
    session_id: str,
    *,
    include_audit: bool,
    language: str,
    context: Any | None = None,
    session_override: dict[str, Any] | None = None,
    audit_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """End-to-end: fetch → render → screenshot → PDF → upload.

    `session_override` + `audit_override` let unit tests inject deterministic
    data without spinning up Catalyst NoSQL. In production they're None.
    """
    export_request_id = str(uuid.uuid4())
    generated_at = _utc_now_iso()

    session = session_override if session_override is not None else _fetch_session(session_id, context=context)
    if not session:
        raise ValueError(f"session not found: {session_id}")
    session.setdefault("session_id", session_id)

    turns = list(session.get("turns") or [])

    # Enrich each turn with embedded snapshots (best-effort)
    for idx, turn in enumerate(turns, start=1):
        _enrich_turn_snapshots(turn, session_id=session_id, turn_idx=idx)

    audit_entries: list[dict[str, Any]] = []
    if include_audit:
        if audit_override is not None:
            audit_entries = audit_override
        else:
            request_ids = [t.get("request_id") for t in turns if t.get("request_id")]
            audit_entries = _fetch_audit_chain(session_id, request_ids, context=context)

    html = render_html(
        session=session,
        turns=turns,
        language=language,
        include_audit=include_audit,
        audit_entries=audit_entries,
        export_request_id=export_request_id,
        generated_at=generated_at,
    )

    pdf_bytes = html_to_pdf(html)

    object_key = f"{STRATUS_PREFIX.strip('/')}/{session_id}.pdf"
    pdf_url = upload_to_stratus(pdf_bytes, object_key, context=context)

    return {
        "pdf_url": pdf_url,
        "size_bytes": len(pdf_bytes),
        "generated_at": generated_at,
        "session_id": session_id,
        "turns": len(turns),
        "export_request_id": export_request_id,
        "object_key": object_key,
    }


# ---------------------------------------------------------------------------
# Catalyst Advanced I/O handler
# ---------------------------------------------------------------------------

def handler(context: Any, basic_io: Any = None) -> Any:
    """POST entry point. See module docstring for request/response shapes."""
    start_ms = time.time()

    # Resolve (request, response) across Catalyst runtime versions
    if basic_io is not None and (hasattr(basic_io, "req") or hasattr(basic_io, "request")):
        request = getattr(basic_io, "req", None) or getattr(basic_io, "request", None)
        response = getattr(basic_io, "res", None) or getattr(basic_io, "response", None)
    else:
        request, response = context, basic_io

    try:
        body = _parse_body(request)
        session_id = str(body.get("session_id") or "").strip()
        include_audit = bool(body.get("include_audit", True))
        language = str(body.get("language") or "both").lower()
        if language not in ("kn", "en", "both"):
            language = "both"

        if not session_id:
            return _write_response(response, 400, {
                "ok": False,
                "service": SERVICE_NAME,
                "version": APP_VERSION,
                "error": "session_id is required",
                "timestamp_utc": _utc_now_iso(),
            })

        result = export_session_pdf(
            session_id,
            include_audit=include_audit,
            language=language,
            context=context if hasattr(context, "__class__") else None,
        )

        latency_ms = int((time.time() - start_ms) * 1000)
        logger.info(
            "pdf export session_id=%s lang=%s audit=%s turns=%d size=%d latency_ms=%d",
            session_id, language, include_audit,
            result["turns"], result["size_bytes"], latency_ms,
        )

        return _write_response(response, 200, {
            "ok": True,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "session_id": session_id,
            "pdf_url": result["pdf_url"],
            "size_bytes": result["size_bytes"],
            "generated_at": result["generated_at"],
            "turns": result["turns"],
            "export_request_id": result["export_request_id"],
            "object_key": result["object_key"],
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })

    except ValueError as exc:
        latency_ms = int((time.time() - start_ms) * 1000)
        logger.warning("pdf export bad request: %s", exc)
        return _write_response(response, 404, {
            "ok": False,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "error": str(exc),
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        latency_ms = int((time.time() - start_ms) * 1000)
        logger.exception("pdf exporter failed")
        return _write_response(response, 500, {
            "ok": False,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })
