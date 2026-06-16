"""KSP Saathi — RAG retriever Catalyst Function.

Advanced I/O endpoint that resolves semantic-search queries against the
case-narrative corpus (Kannada + English). Implements the dual-path
strategy locked in design.md Section 10 + the embedder gap noted in
Section 17 (item 4 — Catalyst QuickML RAG embedder opaque/non-configurable):

    1. PRIMARY: try Catalyst QuickML RAG (`/v1/rag/search`-style endpoint)
    2. FALLBACK: Gemini embedding (`gemini-embedding-001`, RETRIEVAL_QUERY)
                 then cosine-similarity against the pre-embedded narratives
                 stored in Catalyst NoSQL table `narrative_embeddings`.

The fallback is the safety net for Kannada quality. The env flag
`USE_GEMINI_EMBEDDINGS=true` lets ops force the fallback path during
A/B tests without redeploying.

Request shape (POST):
    {
        "request_id": "...",
        "query": "vehicle theft near Indiranagar",
        "language": "en" | "kn" | "auto",
        "top_k": 5,
        "filters": {
            "crime_type": "vehicle_theft",
            "district": "Bengaluru Urban",
            "date_range": {"from": "2025-01-01", "to": "2026-06-13"}
        }
    }

Response shape:
    {
        "request_id": "...",
        "passages": [
            {
                "fir_no": "BLR/IND/2025/0142",
                "narrative": "...",
                "narrative_kannada": "...",
                "score": 0.87,
                "metadata": {"crime_type": "...", "district": "...", "date": "..."}
            },
            ...
        ],
        "method_used": "quickml" | "gemini_embed",
        "latency_ms": 412
    }
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("ksp_saathi.rag_retriever")
logger.setLevel(logging.INFO)

APP_VERSION = "0.1.0"
SERVICE_NAME = "ksp-saathi-rag-retriever"

# ---------------------------------------------------------------------------
# Path setup so `shared/` (sibling of `functions/`) is importable both in
# local pytest runs and in deployed bundles where Catalyst flattens the
# dependency tree.
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


# ---------------------------------------------------------------------------
# Configuration knobs (env-overridable)
# ---------------------------------------------------------------------------

USE_GEMINI_EMBEDDINGS = os.getenv("USE_GEMINI_EMBEDDINGS", "false").lower() in ("1", "true", "yes")
QUICKML_RAG_ENDPOINT = os.getenv("QUICKML_RAG_ENDPOINT", "")  # e.g. https://.../v1/rag/search
QUICKML_RAG_API_KEY = os.getenv("QUICKML_RAG_API_KEY", "")
QUICKML_RAG_CORPUS_ID = os.getenv("QUICKML_RAG_CORPUS_ID", "case_narratives")
QUICKML_RAG_TIMEOUT_S = float(os.getenv("QUICKML_RAG_TIMEOUT_S", "4.0"))
QUICKML_RAG_MIN_SCORE = float(os.getenv("QUICKML_RAG_MIN_SCORE", "0.35"))

NARRATIVE_TABLE = os.getenv("CATALYST_NARRATIVE_TABLE", "narrative_embeddings")
DEFAULT_TOP_K = int(os.getenv("RAG_DEFAULT_TOP_K", "5"))
MAX_TOP_K = int(os.getenv("RAG_MAX_TOP_K", "25"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_body(request: Any) -> dict[str, Any]:
    """Extract the JSON body from a Catalyst Advanced I/O request, tolerantly.

    Supports: real Catalyst Flask-like request objects, raw dicts (unit tests),
    and dict-shaped fakes that just have `.body` attached.
    """
    if request is None:
        return {}
    if isinstance(request, dict):
        return request
    # Common shapes Catalyst's runtime exposes
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
    """Send the JSON response; tolerate multiple Catalyst response shapes."""
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
# Filter logic — applied identically to QuickML hits and Gemini-embedding hits
# ---------------------------------------------------------------------------

def _passes_filters(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Return True iff `meta` matches every filter constraint."""
    if not filters:
        return True

    crime_type = filters.get("crime_type")
    if crime_type and str(meta.get("crime_type", "")).lower() != str(crime_type).lower():
        return False

    district = filters.get("district")
    if district and str(meta.get("district", "")).lower() != str(district).lower():
        return False

    date_range = filters.get("date_range") or {}
    if date_range:
        ds = meta.get("date") or meta.get("date_registered") or ""
        if isinstance(ds, str) and ds:
            try:
                d = datetime.fromisoformat(ds[:10])
            except ValueError:
                return True  # unparseable dates pass — don't drop legitimate hits
            frm = date_range.get("from")
            to = date_range.get("to")
            if frm:
                try:
                    if d < datetime.fromisoformat(str(frm)[:10]):
                        return False
                except ValueError:
                    pass
            if to:
                try:
                    if d > datetime.fromisoformat(str(to)[:10]):
                        return False
                except ValueError:
                    pass
    return True


# ---------------------------------------------------------------------------
# Path 1 — Catalyst QuickML RAG
# ---------------------------------------------------------------------------

def _try_quickml(query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Attempt the Catalyst QuickML RAG endpoint. Returns None on hard fail.

    The endpoint contract (per Catalyst docs at time of writing):
        POST {QUICKML_RAG_ENDPOINT}
        Authorization: Zoho-oauthtoken {QUICKML_RAG_API_KEY}
        body: { "corpus_id", "query", "top_k", "filters" }

    Returns a list of dicts with fir_no/narrative/score, or None when the
    endpoint isn't configured / errored / returned low-quality results.
    """
    if not QUICKML_RAG_ENDPOINT or not QUICKML_RAG_API_KEY:
        logger.info("QuickML RAG not configured — using Gemini fallback")
        return None

    try:
        # `requests` is part of Catalyst's base runtime, but guard the import
        # so a barebones bundle still loads.
        import requests  # type: ignore
    except ImportError:
        logger.warning("requests not available — skipping QuickML path")
        return None

    payload = {
        "corpus_id": QUICKML_RAG_CORPUS_ID,
        "query": query,
        "top_k": max(top_k * 2, top_k + 3),  # over-fetch so filters can prune
        "filters": filters or {},
    }
    headers = {
        "Authorization": f"Zoho-oauthtoken {QUICKML_RAG_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            QUICKML_RAG_ENDPOINT, json=payload, headers=headers, timeout=QUICKML_RAG_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — network errors → fallback
        logger.warning("QuickML RAG request failed: %s — falling back", exc)
        return None

    if resp.status_code >= 400:
        logger.warning("QuickML RAG HTTP %d: %s", resp.status_code, resp.text[:200])
        return None

    try:
        data = resp.json()
    except ValueError:
        logger.warning("QuickML RAG returned non-JSON; falling back")
        return None

    raw_hits = data.get("results") or data.get("hits") or data.get("passages") or []
    if not raw_hits:
        return []

    # Normalise the QuickML response shape. We assume each hit carries
    # fir_no + score + text + metadata. We re-apply filters defensively
    # in case QuickML ignored them (early-version endpoints sometimes do).
    normalised: list[dict[str, Any]] = []
    for hit in raw_hits:
        meta = hit.get("metadata") or {}
        if not _passes_filters(meta, filters):
            continue
        score = float(hit.get("score") or hit.get("similarity") or 0.0)
        # Normalise QuickML's raw score to a 0-1 cosine-like range. Most QuickML
        # endpoints return [-1, 1]; some return [0, 1]; clamp either way.
        if score < 0:
            score = (score + 1.0) / 2.0
        score = max(0.0, min(1.0, score))
        normalised.append({
            "fir_no": hit.get("fir_no") or meta.get("fir_no") or hit.get("id") or "",
            "narrative": hit.get("text") or hit.get("narrative") or "",
            "narrative_kannada": hit.get("text_kn") or hit.get("narrative_kannada") or meta.get("text_kn", ""),
            "score": round(score, 4),
            "metadata": {
                "crime_type": meta.get("crime_type"),
                "district": meta.get("district"),
                "date": meta.get("date") or meta.get("date_registered"),
                **{k: v for k, v in meta.items() if k not in {"crime_type", "district", "date"}},
            },
        })

    # Quality gate — if the best hit's score is below the threshold, treat as
    # low-confidence and surface that so the caller may prefer the fallback.
    if normalised and normalised[0]["score"] < QUICKML_RAG_MIN_SCORE:
        logger.info(
            "QuickML top score %.3f below threshold %.3f — escalating to fallback",
            normalised[0]["score"], QUICKML_RAG_MIN_SCORE,
        )
        return None

    return normalised[:top_k]


# ---------------------------------------------------------------------------
# Path 2 — Gemini embeddings + cosine over Catalyst NoSQL corpus
# ---------------------------------------------------------------------------

def _fetch_corpus_rows(context: Any | None) -> list[dict[str, Any]]:
    """Load all pre-embedded narratives from Catalyst NoSQL.

    Schema (per design.md §7.2):
        { fir_no, embedding: list[float], text, text_kn, crime_type, district, date }

    For demo-scale corpora (50K records) this is fine in-memory. At
    production scale we'd swap to a vector index (FAISS / pgvector). The
    function is structured so that swap is one method, not a rewrite.
    """
    try:
        from shared.catalyst_client import get_nosql  # type: ignore
    except ImportError as exc:
        logger.error("catalyst_client unavailable: %s", exc)
        return []

    try:
        nosql = get_nosql(context=context)
        table = nosql.table(NARRATIVE_TABLE)
    except Exception as exc:  # noqa: BLE001
        logger.error("could not open NoSQL table %s: %s", NARRATIVE_TABLE, exc)
        return []

    # zcatalyst-sdk NoSQL exposes a few different read shapes depending on
    # SDK version (`fetch_all_items`, `get_iterable_items`, `query_items`).
    # We try them in order so the function isn't pinned to one SDK rev.
    rows: list[dict[str, Any]] = []
    fetched = None
    for fn_name in ("fetch_all_items", "get_iterable_items", "get_all_items"):
        fn = getattr(table, fn_name, None)
        if callable(fn):
            try:
                fetched = fn()
                break
            except Exception as exc:  # noqa: BLE001
                logger.debug("NoSQL %s failed: %s — trying next reader", fn_name, exc)
                continue

    if fetched is None:
        logger.warning("no NoSQL reader worked on table %s", NARRATIVE_TABLE)
        return []

    # `fetched` may be a generator, a list, or a dict-with-items wrapper.
    if isinstance(fetched, dict):
        fetched = fetched.get("items") or fetched.get("data") or []

    for raw in fetched:
        if isinstance(raw, dict):
            item = raw.get("item") if "item" in raw else raw
        else:
            item = getattr(raw, "item", raw)
        if isinstance(item, dict) and item.get("embedding"):
            rows.append(item)

    logger.info("loaded %d narrative rows from %s", len(rows), NARRATIVE_TABLE)
    return rows


def _gemini_fallback(
    query: str,
    top_k: int,
    filters: dict[str, Any],
    context: Any | None,
) -> list[dict[str, Any]]:
    """Embed query with Gemini, cosine against NoSQL corpus, return top-k."""
    try:
        from .embedder import cosine_similarity, embed_query  # type: ignore
    except ImportError:
        # Direct-script imports (pytest with rootdir at function folder)
        from embedder import cosine_similarity, embed_query  # type: ignore

    q_vec = embed_query(query)
    if not q_vec:
        logger.warning("empty query embedding — returning no passages")
        return []

    rows = _fetch_corpus_rows(context)
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        emb = row.get("embedding") or []
        if not emb:
            continue
        meta = {
            "crime_type": row.get("crime_type"),
            "district": row.get("district"),
            "date": row.get("date") or row.get("date_registered"),
        }
        if not _passes_filters(meta, filters):
            continue
        score = cosine_similarity(q_vec, emb)
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    passages: list[dict[str, Any]] = []
    for score, row in scored[:top_k]:
        passages.append({
            "fir_no": row.get("fir_no", ""),
            "narrative": row.get("text") or row.get("narrative") or "",
            "narrative_kannada": row.get("text_kn") or row.get("narrative_kannada") or "",
            "score": round(max(0.0, min(1.0, (score + 1.0) / 2.0 if score < 0 else score)), 4),
            "metadata": {
                "crime_type": row.get("crime_type"),
                "district": row.get("district"),
                "date": row.get("date") or row.get("date_registered"),
            },
        })
    return passages


# ---------------------------------------------------------------------------
# Core retrieval entry — exposed for direct testing
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    *,
    language: str = "auto",
    top_k: int = DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
    context: Any | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Run the dual-path retrieval and return (passages, method_used).

    Method-used is "quickml" when the QuickML RAG endpoint produced
    above-threshold results, otherwise "gemini_embed".
    """
    filters = filters or {}
    top_k = max(1, min(int(top_k or DEFAULT_TOP_K), MAX_TOP_K))

    # Forced fallback for A/B testing
    if USE_GEMINI_EMBEDDINGS:
        logger.info("USE_GEMINI_EMBEDDINGS=true — bypassing QuickML")
        passages = _gemini_fallback(query, top_k, filters, context)
        return passages, "gemini_embed"

    quickml_hits = _try_quickml(query, top_k, filters)
    if quickml_hits:
        return quickml_hits, "quickml"

    passages = _gemini_fallback(query, top_k, filters, context)
    return passages, "gemini_embed"


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
        request_id = str(body.get("request_id") or "")
        query = str(body.get("query") or "").strip()
        language = str(body.get("language") or "auto")
        top_k = int(body.get("top_k") or DEFAULT_TOP_K)
        filters = body.get("filters") or {}

        if not query:
            return _write_response(response, 400, {
                "ok": False,
                "service": SERVICE_NAME,
                "version": APP_VERSION,
                "request_id": request_id,
                "error": "query is required",
                "timestamp_utc": _utc_now_iso(),
            })

        passages, method_used = retrieve(
            query,
            language=language,
            top_k=top_k,
            filters=filters,
            context=context if hasattr(context, "__class__") else None,
        )

        latency_ms = int((time.time() - start_ms) * 1000)
        logger.info(
            "rag retrieve request_id=%s lang=%s top_k=%d method=%s hits=%d latency_ms=%d",
            request_id, language, top_k, method_used, len(passages), latency_ms,
        )

        return _write_response(response, 200, {
            "ok": True,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "request_id": request_id,
            "passages": passages,
            "method_used": method_used,
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })

    except Exception as exc:  # noqa: BLE001 — top-level safety net
        latency_ms = int((time.time() - start_ms) * 1000)
        logger.exception("rag retriever failed")
        return _write_response(response, 500, {
            "ok": False,
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
            "latency_ms": latency_ms,
            "timestamp_utc": _utc_now_iso(),
        })
