"""Synthesizer — KSP Saathi Catalyst Advanced I/O Function.

Turns ``tool_results`` from the orchestrator (SQL rows, Cypher edges, RAG
chunks, forecasts) into a streaming natural-language answer plus a
visualization spec that the React frontend uses to update the map / network
graph / chart panels live.

Streams Server-Sent Events:

    data: {"type": "text_chunk", "content": "...partial..."}
    data: {"type": "viz_spec", "map": {...}, "graph": {...}, "chart": {...}}
    data: {"type": "audit_chain", "steps": [...]}
    data: {"type": "done"}

Model selection (see design.md §10 + CLAUDE.md LLM strategy):
  * Kannada query OR ``router_decision.complexity == "high"`` → Gemini 2.5 Pro
  * Otherwise → Qwen 2.5 14B Instruct on Catalyst QuickML LLM Serving

The function ALWAYS writes a final audit entry to Catalyst NoSQL (collection
``saathi_audit_log``) holding the full transcript. Audit writes never block
the SSE stream — they fan out on a background thread.

Catalyst Advanced I/O contract:

    The function receives the WSGI-style ``context`` + ``basic_io`` pair.
    Returning a generator + the right Content-Type makes Catalyst proxy
    the stream verbatim to the caller (SSE-compatible).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Generator, Iterable

# ---------------------------------------------------------------------------
# Imports from shared/ — make the parent backend dir importable
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Prefer the shared prompts module if it's been promoted there; otherwise
# fall back to the local copy that ships alongside this function.
try:
    from shared.prompts import synthesizer_prompt, system_instruction  # type: ignore
except Exception:  # pragma: no cover — wired locally during dev
    from prompts_synthesizer import synthesizer_prompt, system_instruction  # type: ignore

try:
    from shared.gemini_client import get_text_client, GeminiClientError  # type: ignore
except Exception:  # pragma: no cover
    get_text_client = None  # type: ignore[assignment]

    class GeminiClientError(RuntimeError):  # type: ignore[no-redef]
        pass


logger = logging.getLogger("ksp_saathi.synthesizer")
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# ---------------------------------------------------------------------------
# Tunables (env-overridable so demo-day operators can hot-swap models)
# ---------------------------------------------------------------------------

QWEN_ENDPOINT = os.getenv(
    "QWEN_QUICKML_ENDPOINT",
    "https://quickml.catalyst.zoho.in/llm/v1/chat/completions",
)
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-14b-instruct")
QWEN_API_KEY = os.getenv("QWEN_API_KEY") or os.getenv("CATALYST_QUICKML_API_KEY")
QWEN_TIMEOUT_S = float(os.getenv("QWEN_TIMEOUT_S", "45"))

GEMINI_MODEL = os.getenv("GEMINI_SYNTH_MODEL", "gemini-2.5-pro")

AUDIT_COLLECTION = os.getenv("AUDIT_NOSQL_COLLECTION", "saathi_audit_log")

# Sentence boundary regex — matches the punctuation, then keeps trailing
# whitespace so the consumer can re-join chunks losslessly.
_SENTENCE_RE = re.compile(r"[^.!?।॥।]*[.!?।॥।]+\s*", re.UNICODE)


# ---------------------------------------------------------------------------
# Models & helpers
# ---------------------------------------------------------------------------

@dataclass
class SynthRequest:
    request_id: str
    query: str
    language: str
    router_decision: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    user_id: str | None = None
    role: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SynthRequest":
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        query = (payload.get("query") or "").strip()
        if not query:
            raise ValueError("'query' is required and must be non-empty")
        return cls(
            request_id=payload.get("request_id") or str(uuid.uuid4()),
            query=query,
            language=(payload.get("language") or "en").lower(),
            router_decision=payload.get("router_decision") or {},
            tool_results=list(payload.get("tool_results") or []),
            user_id=payload.get("user_id"),
            role=payload.get("role"),
        )


def _is_kannada(lang: str) -> bool:
    return (lang or "").lower().startswith("kn")


def _is_complex(router_decision: dict[str, Any] | None) -> bool:
    if not router_decision:
        return False
    if router_decision.get("complexity") in {"high", "complex"}:
        return True
    intents = router_decision.get("intents") or []
    if isinstance(intents, list) and len(intents) >= 3:
        return True
    if router_decision.get("intent") == "mixed":
        return True
    return False


def _pick_model(req: SynthRequest) -> tuple[str, str]:
    """Return ``(family, model_id)`` — ``family`` ∈ {"gemini", "qwen"}."""
    if _is_kannada(req.language) or _is_complex(req.router_decision):
        return "gemini", GEMINI_MODEL
    return "qwen", QWEN_MODEL


def _sse(event: dict[str, Any]) -> bytes:
    """Format a single SSE ``data:`` line."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# Streaming primitives — split a token stream into sentence-aligned chunks
# ---------------------------------------------------------------------------

def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """Greedy split on sentence enders. Returns (complete, remainder)."""
    if not buffer:
        return [], ""
    matches = list(_SENTENCE_RE.finditer(buffer))
    if not matches:
        return [], buffer
    last_end = matches[-1].end()
    complete = [m.group(0) for m in matches]
    remainder = buffer[last_end:]
    return complete, remainder


def _extract_viz(text: str) -> tuple[str, dict[str, Any] | None]:
    """Strip the ``<viz>{...}</viz>`` block and return ``(prose, viz)``."""
    if not text:
        return text, None
    m = re.search(r"<viz>\s*(\{.*?\})\s*</viz>", text, re.DOTALL)
    if not m:
        return text, None
    raw = m.group(1)
    prose = (text[:m.start()] + text[m.end():]).strip()
    try:
        viz = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("viz JSON parse failed: %s", exc)
        viz = None
    return prose, viz


# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

def _stream_gemini(prompt: str, system: str, *, model: str) -> Iterable[str]:
    """Yield raw text deltas from Gemini 2.5 Pro."""
    if get_text_client is None:
        raise GeminiClientError("shared.gemini_client unavailable in this bundle")
    client = get_text_client(model=model)
    # The shared wrapper exposes blocking + async generate; for SSE we use the
    # underlying SDK directly so we can stream deltas.
    raw = getattr(client, "_raw", None) or getattr(client, "raw_client", None)
    if raw is None:  # pragma: no cover — defensive
        full = client.generate(prompt, system=system, temperature=0.3,
                               max_output_tokens=2048)
        yield full
        return

    try:
        from google.genai import types as genai_types  # type: ignore
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.3,
            max_output_tokens=2048,
        )
        stream = raw.models.generate_content_stream(
            model=model, contents=prompt, config=config,
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text
    except Exception as exc:  # pragma: no cover — surfaced to caller
        raise GeminiClientError(f"Gemini streaming failed: {exc}") from exc


def _stream_qwen(prompt: str, system: str, *, model: str) -> Iterable[str]:
    """Yield text deltas from Qwen 2.5 14B on Catalyst QuickML.

    Uses the OpenAI-compatible ``/chat/completions`` endpoint with
    ``stream=true`` — Catalyst QuickML LLM Serving exposes this shape.
    """
    import httpx  # local import keeps cold-start small

    if not QWEN_API_KEY:
        raise RuntimeError("QWEN_API_KEY / CATALYST_QUICKML_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    with httpx.stream(
        "POST", QWEN_ENDPOINT, headers=headers, json=body, timeout=QWEN_TIMEOUT_S,
    ) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                yield piece


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _build_audit_steps(
    req: SynthRequest,
    *,
    model_family: str,
    model_id: str,
    sources: list[str],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    rd = req.router_decision or {}
    steps.append({
        "step": "intent_router",
        "intent": rd.get("intent") or rd.get("intents") or "unknown",
        "confidence": rd.get("confidence"),
        "model": rd.get("model") or "qwen2.5-7b-instruct",
    })
    for tr in req.tool_results:
        steps.append({
            "step": "tool_call",
            "tool": tr.get("tool"),
            "status": tr.get("status") or ("ok" if tr.get("rows") is not None
                                            or tr.get("data") is not None
                                            else "empty"),
            "latency_ms": tr.get("latency_ms"),
            "source_count": _count_sources(tr),
        })
    steps.append({
        "step": "synthesizer",
        "model_family": model_family,
        "model": model_id,
        "language": req.language,
        "sources": sources,
    })
    return steps


def _count_sources(tool_result: dict[str, Any]) -> int:
    for key in ("rows", "data", "chunks", "edges", "nodes", "points"):
        value = tool_result.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _collect_sources(tool_results: Iterable[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for tr in tool_results or []:
        for key in ("rows", "data", "chunks"):
            value = tr.get(key)
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        sid = (row.get("fir_no") or row.get("id")
                               or row.get("source_id") or row.get("chunk_id"))
                        if sid:
                            out.append(str(sid))
    # Preserve order, deduplicate.
    seen = set()
    deduped = []
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def _write_audit(entry: dict[str, Any]) -> None:
    """Best-effort write to Catalyst NoSQL. Never raises into the SSE stream."""
    try:
        import zcatalyst_sdk  # type: ignore
        app = zcatalyst_sdk.initialize()
        nosql = app.nosql()
        table = nosql.table(AUDIT_COLLECTION)
        table.insert_row(entry)
        logger.info("Audit row written for request_id=%s", entry.get("request_id"))
    except Exception as exc:  # noqa: BLE001 — audit must never crash the response
        logger.error("Audit write failed: %s", exc, exc_info=True)


def _write_audit_async(entry: dict[str, Any]) -> None:
    threading.Thread(target=_write_audit, args=(entry,), daemon=True).start()


# ---------------------------------------------------------------------------
# Core generator — yields SSE bytes
# ---------------------------------------------------------------------------

def synthesize_stream(req: SynthRequest) -> Generator[bytes, None, None]:
    started = time.time()
    family, model_id = _pick_model(req)
    logger.info("synthesize request_id=%s lang=%s model=%s/%s",
                req.request_id, req.language, family, model_id)

    system = system_instruction(req.language)
    user_prompt = synthesizer_prompt(
        query=req.query,
        lang=req.language,
        tool_results=req.tool_results,
        router_decision=req.router_decision,
    )

    if family == "gemini":
        stream = _stream_gemini(user_prompt, system, model=model_id)
    else:
        stream = _stream_qwen(user_prompt, system, model=model_id)

    text_buffer = ""
    full_text_parts: list[str] = []
    in_viz = False

    try:
        for delta in stream:
            if not delta:
                continue
            full_text_parts.append(delta)
            text_buffer += delta

            # If we have started emitting the <viz> block, hold back until
            # the closing tag so we never leak partial JSON to the client.
            if "<viz>" in text_buffer and "</viz>" not in text_buffer:
                in_viz = True
                continue
            if in_viz and "</viz>" not in text_buffer:
                continue

            # Hand back sentence-aligned chunks for nicer TTS pacing.
            complete, remainder = _split_sentences(text_buffer)
            for sentence in complete:
                prose_only, _ = _extract_viz(sentence)
                if prose_only.strip():
                    yield _sse({"type": "text_chunk", "content": prose_only})
            text_buffer = remainder
            in_viz = "<viz>" in text_buffer and "</viz>" not in text_buffer
    except Exception as exc:
        logger.error("LLM stream failed: %s\n%s", exc, traceback.format_exc())
        yield _sse({
            "type": "error",
            "code": "llm_stream_failed",
            "message": str(exc),
        })
        yield _sse({"type": "done"})
        return

    # Flush any prose tail (no sentence ender).
    tail_prose, _ = _extract_viz(text_buffer)
    if tail_prose.strip():
        yield _sse({"type": "text_chunk", "content": tail_prose})

    # Extract the viz spec from the concatenated full text.
    full_text = "".join(full_text_parts)
    _, viz = _extract_viz(full_text)
    viz_event: dict[str, Any] = {
        "type": "viz_spec",
        "map": (viz or {}).get("map") if viz else None,
        "graph": (viz or {}).get("graph") if viz else None,
        "chart": (viz or {}).get("chart") if viz else None,
    }
    yield _sse(viz_event)

    # Audit chain.
    sources = _collect_sources(req.tool_results)
    steps = _build_audit_steps(req, model_family=family, model_id=model_id,
                               sources=sources)
    yield _sse({"type": "audit_chain", "steps": steps})

    elapsed_ms = int((time.time() - started) * 1000)
    yield _sse({"type": "done", "latency_ms": elapsed_ms})

    # Fire-and-forget audit write.
    final_prose, _ = _extract_viz(full_text)
    _write_audit_async({
        "request_id": req.request_id,
        "user_id": req.user_id,
        "role": req.role,
        "language": req.language,
        "raw_query": req.query,
        "router_decision": req.router_decision,
        "tool_results_summary": [
            {"tool": tr.get("tool"), "rows": _count_sources(tr)}
            for tr in req.tool_results
        ],
        "model_family": family,
        "model": model_id,
        "sources": sources,
        "response_text": final_prose,
        "viz_spec": viz,
        "audit_steps": steps,
        "latency_ms": elapsed_ms,
        "ts": int(time.time() * 1000),
    })


# ---------------------------------------------------------------------------
# Catalyst Advanced I/O entrypoint
# ---------------------------------------------------------------------------

SSE_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering
}


def _parse_body(basic_io: Any) -> dict[str, Any]:
    """Read JSON body from the Catalyst Advanced I/O request envelope."""
    # Catalyst Advanced I/O exposes ``basic_io.get_argument`` for query
    # params and ``basic_io.get_request_body`` for the raw body. We try a
    # couple of shapes so the same code works in both the new SDK and
    # local pytest harness.
    if hasattr(basic_io, "get_request_body"):
        raw = basic_io.get_request_body()
    elif hasattr(basic_io, "body"):
        raw = basic_io.body
    elif isinstance(basic_io, dict):
        raw = basic_io.get("body")
    else:
        raw = None

    if raw is None:
        return {}
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    raise ValueError(f"Unsupported request body type: {type(raw)!r}")


def _write_response(basic_io: Any, status: int,
                    body_iter: Iterable[bytes],
                    headers: dict[str, str] | None = None) -> Generator[bytes, None, None]:
    """Push headers + status to the Catalyst response and yield the body."""
    hdrs = dict(headers or SSE_HEADERS)
    # New Catalyst Python SDK shape.
    if hasattr(basic_io, "set_status"):
        try:
            basic_io.set_status(status)
        except Exception:  # pragma: no cover
            pass
    if hasattr(basic_io, "set_header"):
        for k, v in hdrs.items():
            try:
                basic_io.set_header(k, v)
            except Exception:  # pragma: no cover
                pass
    elif hasattr(basic_io, "headers"):
        try:
            basic_io.headers.update(hdrs)
        except Exception:  # pragma: no cover
            pass

    for chunk in body_iter:
        if hasattr(basic_io, "write"):
            try:
                basic_io.write(chunk)
                continue
            except Exception:  # pragma: no cover
                pass
        yield chunk


def handler(context: Any, basic_io: Any) -> Generator[bytes, None, None]:
    """Catalyst Advanced I/O entrypoint.

    Returns a generator of bytes — Catalyst forwards each yielded chunk to
    the client as the SSE response body. ``Content-Type`` is set via
    ``basic_io.set_header`` so browsers / Vercel AI SDK consume it as a
    Server-Sent Events stream.
    """
    try:
        payload = _parse_body(basic_io)
        req = SynthRequest.from_payload(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        error_iter = iter([
            _sse({"type": "error", "code": "bad_request", "message": str(exc)}),
            _sse({"type": "done"}),
        ])
        yield from _write_response(basic_io, 400, error_iter)
        return

    yield from _write_response(basic_io, 200, synthesize_stream(req))


# Alias expected by some Catalyst function templates.
def main(context: Any, basic_io: Any) -> Generator[bytes, None, None]:
    yield from handler(context, basic_io)


__all__ = ["handler", "main", "synthesize_stream", "SynthRequest"]
