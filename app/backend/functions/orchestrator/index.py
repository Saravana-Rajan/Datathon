"""KSP Saathi — Orchestrator (Catalyst Advanced I/O Function).

This is the BRAIN of Yaksha. It REPLACES the Catalyst Circuits YAML flow
because Catalyst Circuits is not available in the India DC (see
``design.md`` §18 Decision Log 2026-06-16).

Spec source-of-truth: ``app/backend/circuits/main-query-flow.yaml`` — this
module implements the same 4-step pipeline in Python, with proper
async/await fan-out via ``asyncio.gather()``.

Pipeline (mirrors main-query-flow.yaml):

    Step 1 — Generate ``request_id``; emit ``started`` SSE event.

    Step 2 — Call ``intent-router`` (unary, ~300ms). Emit ``routed`` event
             with intent + detected language.

    Step 3 — Build a parallel task list from the RouterDecision and run
             every applicable specialist concurrently via
             ``asyncio.gather()``:

                tabular_query / geo_query   -> sql-generator
                graph_query                 -> cypher-generator
                lookup  / semantic          -> rag-retriever
                predictive_query            -> predictive-service (stub OK)
                mixed                       -> fan-out all relevant tools

             For each tool: emit ``tool_started`` when launched,
             ``tool_done`` with ``ok=true/false`` + ``ms`` on completion.
             A single tool failure DOES NOT abort the pipeline — partial
             results flow into the synthesizer.

    Step 4 — Open a streaming call to ``synthesizer`` and proxy every SSE
             event (``text_chunk``, ``viz_spec``, ``audit_chain``,
             ``done``) verbatim to the client.

    Step 5 — Fire-and-forget call to ``audit-logger`` with the full chain.
             Audit failures NEVER fail the user query.

Hard timeouts:
    Total pipeline: 30s wall clock.
    Per-tool soft timeout: 8s (cancels just that tool, others continue).

SSE event types emitted by THIS module (in addition to whatever the
synthesizer streams):

    data: {"type":"started",      "request_id":"..."}
    data: {"type":"routed",       "intent":"...", "language":"...", "ms":...}
    data: {"type":"tool_started", "tool":"sql-generator"}
    data: {"type":"tool_done",    "tool":"sql-generator", "ok":true, "ms":1234}
    data: {"type":"error",        "stage":"router|tool|synth", "message":"..."}

Then it forwards every event from the synthesizer SSE stream and finally:

    data: {"type":"orchestrator_done", "total_ms":...}

Catalyst Advanced I/O contract: same handler shape as the synthesizer —
``handler(context, basic_io)`` returns a generator of bytes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import traceback
import uuid
from typing import Any, AsyncGenerator, Generator, Iterable

# Make sibling shared/ importable when bundled by Catalyst.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _candidate in (_BACKEND_DIR, _HERE):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import httpx  # noqa: E402

from invoke_helpers import (  # noqa: E402
    InvokeError,
    InvokeHTTPError,
    InvokeTimeout,
    invoke_function,
    invoke_fire_and_forget,
    stream_function,
)

logger = logging.getLogger("ksp_saathi.orchestrator")
if not logger.handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

TOTAL_TIMEOUT_S = float(os.getenv("ORCH_TOTAL_TIMEOUT_S", "30.0"))
TOOL_TIMEOUT_S = float(os.getenv("ORCH_TOOL_TIMEOUT_S", "8.0"))
ROUTER_TIMEOUT_S = float(os.getenv("ORCH_ROUTER_TIMEOUT_S", "5.0"))
SYNTH_TIMEOUT_S = float(os.getenv("ORCH_SYNTH_TIMEOUT_S", "20.0"))
AUDIT_TIMEOUT_S = float(os.getenv("ORCH_AUDIT_TIMEOUT_S", "3.0"))

ALLOWED_ROLES = {
    "constable", "sub_inspector", "inspector",
    "sho", "dcp", "scrb_analyst", "admin", "unknown",
}


# ---------------------------------------------------------------------------
# Intent -> tool mapping (mirrors circuits/main-query-flow.yaml branches)
# ---------------------------------------------------------------------------

def tools_for_intent(intent: str) -> list[str]:
    """Return the list of tool function names to invoke for an intent.

    ``mixed`` fans out the four primary tools so the synthesizer has the
    widest possible evidence base.
    """
    intent = (intent or "").lower().strip()
    if intent == "tabular_query":
        return ["sql-generator"]
    if intent == "geo_query":
        # geo uses sql-generator with mode=geo; the synthesizer handles H3.
        return ["sql-generator"]
    if intent == "graph_query":
        return ["cypher-generator"]
    if intent in ("lookup", "semantic", "semantic_query"):
        return ["rag-retriever"]
    if intent == "predictive_query":
        return ["predictive-service"]
    if intent == "meta_query":
        # Meta queries are answered by the synthesizer from audit history.
        return []
    if intent == "mixed":
        return ["sql-generator", "cypher-generator", "rag-retriever"]
    # Unknown / low-confidence — default to RAG (safest fallback per spec).
    return ["rag-retriever"]


def _tool_payload(
    tool: str,
    *,
    request_id: str,
    router_decision: dict[str, Any],
    raw_query: str,
    user_role: str,
    session_id: str,
) -> dict[str, Any]:
    """Build the request body for one specialist tool."""
    base = {
        "request_id": request_id,
        "session_id": session_id,
        "user_role": user_role,
        "normalized_query": router_decision.get("normalized_query") or raw_query,
        "entities": router_decision.get("entities") or {},
        "language": router_decision.get("language") or "en",
    }
    if tool == "sql-generator":
        intent = (router_decision.get("intent") or "").lower()
        base["mode"] = "geo" if intent == "geo_query" else "tabular"
    elif tool == "rag-retriever":
        base["top_k"] = 8
    return base


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(event: dict[str, Any]) -> bytes:
    """Encode one SSE ``data:`` line."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# Step runners
# ---------------------------------------------------------------------------

async def _run_router(
    client: httpx.AsyncClient,
    *,
    request_id: str,
    query: str,
    language_hint: str,
    session_id: str,
    user_role: str,
) -> dict[str, Any]:
    """Step 2 — call intent-router. Raises on hard failure."""
    payload = {
        "query": query,
        "language_hint": language_hint,
        "session_id": session_id,
        "user_role": user_role,
        "request_id": request_id,
    }
    return await invoke_function(
        "intent-router",
        payload,
        timeout=ROUTER_TIMEOUT_S,
        client=client,
    )


async def _run_one_tool(
    tool: str,
    payload: dict[str, Any],
    *,
    client: httpx.AsyncClient,
) -> tuple[str, dict[str, Any], int, bool, str | None]:
    """Run a single specialist tool.

    Returns ``(tool, result_dict, latency_ms, ok, error_message)``.
    Never raises — failures are encoded into the return tuple so
    ``asyncio.gather`` can collect partial successes.
    """
    started = time.perf_counter()
    try:
        result = await invoke_function(
            tool,
            payload,
            timeout=TOOL_TIMEOUT_S,
            client=client,
        )
    except InvokeTimeout as exc:
        ms = int((time.perf_counter() - started) * 1000)
        logger.warning("tool=%s TIMEOUT after %dms: %s", tool, ms, exc)
        return tool, {}, ms, False, f"timeout: {exc}"
    except InvokeHTTPError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        logger.warning("tool=%s HTTP %d: %s", tool, exc.status, exc.body[:120])
        return tool, {}, ms, False, f"http_{exc.status}: {exc.body[:120]}"
    except InvokeError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        logger.warning("tool=%s ERROR: %s", tool, exc)
        return tool, {}, ms, False, str(exc)
    except Exception as exc:  # noqa: BLE001 — last-ditch safety net
        ms = int((time.perf_counter() - started) * 1000)
        logger.error("tool=%s CRASH: %s", tool, exc, exc_info=True)
        return tool, {}, ms, False, f"crash: {exc}"

    ms = int((time.perf_counter() - started) * 1000)
    return tool, result, ms, True, None


# ---------------------------------------------------------------------------
# Main orchestration coroutine — pushes SSE events into an asyncio.Queue
# ---------------------------------------------------------------------------

async def _orchestrate(
    queue: asyncio.Queue[bytes | None],
    *,
    query: str,
    language_hint: str,
    session_id: str,
    user_role: str,
) -> None:
    """Run the full pipeline, pushing SSE bytes into ``queue``.

    A trailing ``None`` is pushed to signal the consumer that the stream
    is closed (success or failure).
    """
    pipeline_started = time.perf_counter()
    request_id = str(uuid.uuid4())

    # Single shared httpx client — connection pool re-used by every step.
    async with httpx.AsyncClient(timeout=TOTAL_TIMEOUT_S) as client:
        try:
            await asyncio.wait_for(
                _orchestrate_inner(
                    queue, client,
                    request_id=request_id,
                    query=query,
                    language_hint=language_hint,
                    session_id=session_id,
                    user_role=user_role,
                    pipeline_started=pipeline_started,
                ),
                timeout=TOTAL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            total_ms = int((time.perf_counter() - pipeline_started) * 1000)
            logger.error("Orchestrator hit hard 30s timeout (request_id=%s)", request_id)
            await queue.put(_sse({
                "type": "error",
                "stage": "orchestrator",
                "message": f"total_timeout_{TOTAL_TIMEOUT_S}s",
                "request_id": request_id,
            }))
            await queue.put(_sse({"type": "orchestrator_done", "total_ms": total_ms}))
        except Exception as exc:  # noqa: BLE001
            total_ms = int((time.perf_counter() - pipeline_started) * 1000)
            logger.error("Orchestrator crashed: %s\n%s", exc, traceback.format_exc())
            await queue.put(_sse({
                "type": "error",
                "stage": "orchestrator",
                "message": str(exc),
                "request_id": request_id,
            }))
            await queue.put(_sse({"type": "orchestrator_done", "total_ms": total_ms}))
        finally:
            await queue.put(None)  # sentinel


async def _orchestrate_inner(
    queue: asyncio.Queue[bytes | None],
    client: httpx.AsyncClient,
    *,
    request_id: str,
    query: str,
    language_hint: str,
    session_id: str,
    user_role: str,
    pipeline_started: float,
) -> None:
    # ----- Step 1: emit started ------------------------------------------------
    await queue.put(_sse({"type": "started", "request_id": request_id}))

    # ----- Step 2: intent router ----------------------------------------------
    router_started = time.perf_counter()
    try:
        router_decision = await _run_router(
            client,
            request_id=request_id,
            query=query,
            language_hint=language_hint,
            session_id=session_id,
            user_role=user_role,
        )
    except InvokeTimeout as exc:
        await queue.put(_sse({
            "type": "error", "stage": "router",
            "message": f"router_timeout: {exc}", "request_id": request_id,
        }))
        # Fall through with a minimal default decision so the synthesizer
        # can still produce *something* — empirically better than 500ing.
        router_decision = {
            "intent": "lookup",
            "language": "en",
            "confidence": 0.0,
            "normalized_query": query,
            "entities": {},
            "reasoning": "router_unavailable",
        }
    except InvokeError as exc:
        await queue.put(_sse({
            "type": "error", "stage": "router",
            "message": str(exc), "request_id": request_id,
        }))
        router_decision = {
            "intent": "lookup",
            "language": "en",
            "confidence": 0.0,
            "normalized_query": query,
            "entities": {},
            "reasoning": "router_failed",
        }

    router_ms = int((time.perf_counter() - router_started) * 1000)
    detected_lang = (router_decision.get("language")
                     or router_decision.get("detected_language") or "en")
    intent = router_decision.get("intent") or "lookup"
    # Make the language available downstream under a single canonical key.
    router_decision.setdefault("language", detected_lang)

    await queue.put(_sse({
        "type": "routed",
        "intent": intent,
        "language": detected_lang,
        "confidence": router_decision.get("confidence"),
        "ms": router_ms,
        "request_id": request_id,
    }))

    # ----- Step 3: parallel specialist fan-out --------------------------------
    tools = tools_for_intent(intent)
    tool_results: dict[str, dict[str, Any]] = {}
    tool_errors: list[dict[str, Any]] = []

    if tools:
        # Emit tool_started for each in-flight tool before launching them.
        for tool in tools:
            await queue.put(_sse({
                "type": "tool_started",
                "tool": tool,
                "request_id": request_id,
            }))

        tasks = [
            asyncio.create_task(
                _run_one_tool(
                    tool,
                    _tool_payload(
                        tool,
                        request_id=request_id,
                        router_decision=router_decision,
                        raw_query=query,
                        user_role=user_role,
                        session_id=session_id,
                    ),
                    client=client,
                ),
                name=f"tool:{tool}",
            )
            for tool in tools
        ]

        # Drain completions as they arrive so we can emit tool_done events
        # in completion order (better UX — UI sees fast tools immediately).
        for coro in asyncio.as_completed(tasks):
            tool, result, ms, ok, err = await coro
            if ok:
                tool_results[tool] = result
            else:
                tool_errors.append({"tool": tool, "error": err, "ms": ms})
                # Store an empty marker so synthesizer knows the tool was attempted.
                tool_results[tool] = {"_error": err}

            await queue.put(_sse({
                "type": "tool_done",
                "tool": tool,
                "ok": ok,
                "ms": ms,
                "error": err,
                "request_id": request_id,
            }))
    else:
        logger.info("intent=%s requires no tool fan-out", intent)

    # ----- Step 4: synthesizer (streaming proxy) ------------------------------
    synth_payload = {
        "request_id": request_id,
        "query": query,
        "language": detected_lang,
        "router_decision": router_decision,
        "tool_results": [
            {"tool": name, **(result if isinstance(result, dict) else {"data": result})}
            for name, result in tool_results.items()
        ],
        "warnings": tool_errors,
        "user_id": session_id,
        "role": user_role,
    }

    final_answer_text = ""
    synth_started = time.perf_counter()
    try:
        async with stream_function(
            "synthesizer", synth_payload,
            timeout=SYNTH_TIMEOUT_S, client=client,
        ) as chunks:
            buffer = b""
            async for raw_chunk in chunks:
                buffer += raw_chunk
                # Forward SSE event-by-event so partial UI rendering works.
                while b"\n\n" in buffer:
                    event_bytes, buffer = buffer.split(b"\n\n", 1)
                    event_bytes_full = event_bytes + b"\n\n"
                    # Tap into text_chunk events so we can stash the final
                    # answer for the audit logger — never block the stream.
                    try:
                        for line in event_bytes.split(b"\n"):
                            if line.startswith(b"data:"):
                                obj = json.loads(line[5:].decode("utf-8").strip())
                                if obj.get("type") == "text_chunk":
                                    final_answer_text += obj.get("content") or ""
                    except Exception:  # noqa: BLE001 — best-effort tap
                        pass
                    await queue.put(event_bytes_full)
            # Flush any tail bytes (synthesizer should end on \n\n already).
            if buffer.strip():
                await queue.put(buffer)
    except InvokeTimeout as exc:
        await queue.put(_sse({
            "type": "error", "stage": "synth",
            "message": f"synth_timeout: {exc}", "request_id": request_id,
        }))
    except InvokeHTTPError as exc:
        await queue.put(_sse({
            "type": "error", "stage": "synth",
            "message": f"synth_http_{exc.status}: {exc.body[:120]}",
            "request_id": request_id,
        }))
    except Exception as exc:  # noqa: BLE001
        logger.error("synthesizer proxy crashed: %s\n%s", exc, traceback.format_exc())
        await queue.put(_sse({
            "type": "error", "stage": "synth",
            "message": str(exc), "request_id": request_id,
        }))

    synth_ms = int((time.perf_counter() - synth_started) * 1000)
    total_ms = int((time.perf_counter() - pipeline_started) * 1000)

    # ----- Step 5: audit logger (fire-and-forget) -----------------------------
    audit_payload = {
        "request_id": request_id,
        "session_id": session_id,
        "user_role": user_role,
        "raw_query": query,
        "language": detected_lang,
        "intent_router": router_decision,
        "tool_calls": tool_results,
        "warnings": tool_errors,
        "final_answer": final_answer_text,
        "latency_ms": total_ms,
        "synth_latency_ms": synth_ms,
        "router_latency_ms": router_ms,
        "ts": int(time.time() * 1000),
    }
    # Don't await — schedule on the loop so the user sees orchestrator_done now.
    asyncio.create_task(
        invoke_fire_and_forget(
            "audit-logger", audit_payload,
            timeout=AUDIT_TIMEOUT_S, client=client,
        ),
        name="audit-logger",
    )

    await queue.put(_sse({
        "type": "orchestrator_done",
        "total_ms": total_ms,
        "router_ms": router_ms,
        "synth_ms": synth_ms,
        "tool_count": len(tool_results),
        "warning_count": len(tool_errors),
        "request_id": request_id,
    }))


# ---------------------------------------------------------------------------
# Bridge: pull SSE bytes off the asyncio.Queue and yield them synchronously
# ---------------------------------------------------------------------------

def _drain_queue_blocking(
    queue: asyncio.Queue[bytes | None],
    loop: asyncio.AbstractEventLoop,
) -> Generator[bytes, None, None]:
    """Pull items off ``queue`` one at a time, blocking until each arrives.

    Catalyst Advanced I/O expects a synchronous generator of bytes from
    ``handler``; this bridge lets the async orchestration push events
    into a queue while the handler thread yields them out.
    """
    while True:
        item = asyncio.run_coroutine_threadsafe(queue.get(), loop).result()
        if item is None:
            return
        yield item


async def orchestrate_stream(
    query: str,
    *,
    language_hint: str = "auto",
    session_id: str = "",
    user_role: str = "unknown",
) -> AsyncGenerator[bytes, None]:
    """Async generator interface — used directly from tests.

    Equivalent to ``run_pipeline`` but yields directly without a queue
    bridge — handy for pytest where we already have an event loop.
    """
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def _producer() -> None:
        await _orchestrate(
            queue,
            query=query,
            language_hint=language_hint,
            session_id=session_id,
            user_role=user_role,
        )

    producer = asyncio.create_task(_producer())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await producer


# ---------------------------------------------------------------------------
# Synchronous bridge used by the Catalyst handler
# ---------------------------------------------------------------------------

def run_pipeline_sync(
    *,
    query: str,
    language_hint: str = "auto",
    session_id: str = "",
    user_role: str = "unknown",
) -> Generator[bytes, None, None]:
    """Run the async pipeline from a sync context, yielding SSE bytes.

    Catalyst Advanced I/O dispatches handlers on a thread that's not
    inside an event loop, so we spin up our own loop here and bridge
    asyncio -> generator with a Queue.
    """
    loop = asyncio.new_event_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def _producer() -> None:
        await _orchestrate(
            queue,
            query=query,
            language_hint=language_hint,
            session_id=session_id,
            user_role=user_role,
        )

    # Run the producer on the loop in the background.
    future = asyncio.run_coroutine_threadsafe(_producer(), loop)

    # Run the loop on a worker thread so we can pull from the queue here.
    import threading
    thread = threading.Thread(target=loop.run_forever, daemon=True, name="orch-loop")
    thread.start()
    try:
        yield from _drain_queue_blocking(queue, loop)
        # Make sure the producer finished cleanly (raises on crash).
        future.result(timeout=1.0)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2.0)
        try:
            loop.close()
        except Exception:  # pragma: no cover — defensive
            pass


# ---------------------------------------------------------------------------
# Request parsing + validation
# ---------------------------------------------------------------------------

def _parse_body(basic_io: Any) -> dict[str, Any]:
    """Read JSON body from the Catalyst Advanced I/O request envelope."""
    raw: Any
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


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    query = (payload.get("query") or "").strip()
    if not query:
        raise ValueError("'query' is required and must be non-empty")
    if len(query) > 4000:
        raise ValueError("'query' exceeds 4000 char limit")

    language_hint = (payload.get("language_hint") or "auto").lower().strip()
    if language_hint not in ("auto", "kn", "en", "hi"):
        language_hint = "auto"

    session_id = str(payload.get("session_id") or "")[:128]

    user_role = (payload.get("user_role") or "unknown").lower().strip()
    if user_role not in ALLOWED_ROLES:
        user_role = "unknown"

    return {
        "query": query,
        "language_hint": language_hint,
        "session_id": session_id,
        "user_role": user_role,
    }


# ---------------------------------------------------------------------------
# Response writer — same shape as the synthesizer for consistency
# ---------------------------------------------------------------------------

SSE_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering for true streaming
}


def _write_response(
    basic_io: Any,
    status: int,
    body_iter: Iterable[bytes],
    headers: dict[str, str] | None = None,
) -> Generator[bytes, None, None]:
    hdrs = dict(headers or SSE_HEADERS)
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


# ---------------------------------------------------------------------------
# Catalyst Advanced I/O entrypoint
# ---------------------------------------------------------------------------

def handler(context: Any, basic_io: Any) -> Generator[bytes, None, None]:
    """Catalyst Advanced I/O entrypoint — POST /orchestrator.

    Streams Server-Sent Events for the full query lifecycle.
    """
    try:
        payload = _parse_body(basic_io)
        validated = _validate_payload(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        error_iter = iter([
            _sse({"type": "error", "stage": "validation", "message": str(exc)}),
            _sse({"type": "orchestrator_done", "total_ms": 0}),
        ])
        yield from _write_response(basic_io, 400, error_iter)
        return

    pipeline = run_pipeline_sync(**validated)
    yield from _write_response(basic_io, 200, pipeline)


def main(context: Any, basic_io: Any) -> Generator[bytes, None, None]:
    """Alias expected by some Catalyst function templates."""
    yield from handler(context, basic_io)


__all__ = [
    "handler",
    "main",
    "orchestrate_stream",
    "run_pipeline_sync",
    "tools_for_intent",
]
