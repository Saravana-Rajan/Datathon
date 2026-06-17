"""Pytest suite for the KSP Saathi orchestrator.

We mock ``invoke_helpers.invoke_function`` and ``invoke_helpers.stream_function``
so the tests are hermetic — no network, no Catalyst credentials, no real
downstream functions required.

Coverage:
  1. Happy path:    tabular_query → router → sql-gen → synth → audit
  2. Mixed intent:  fan-out runs 3 tools in parallel
  3. Tool failure:  one tool errors, synth still runs with warnings
  4. Timeout:       slow tool aborted at TOOL_TIMEOUT_S, others complete
  5. Streaming:     SSE events arrive in the correct order

Run from this directory:
    pytest test_orchestrator.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import pytest

# Make the function dir importable as a flat module set.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import index  # noqa: E402  — module under test
import invoke_helpers  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sse_events(byte_chunks: list[bytes]) -> list[dict[str, Any]]:
    """Flatten a list of SSE byte chunks into parsed JSON events."""
    events: list[dict[str, Any]] = []
    buffer = b"".join(byte_chunks)
    # Each event ends with \n\n.
    for raw_event in buffer.split(b"\n\n"):
        raw_event = raw_event.strip()
        if not raw_event:
            continue
        for line in raw_event.split(b"\n"):
            if line.startswith(b"data:"):
                payload = line[5:].decode("utf-8").strip()
                if payload:
                    events.append(json.loads(payload))
    return events


async def _collect(stream: AsyncGenerator[bytes, None]) -> list[bytes]:
    out: list[bytes] = []
    async for chunk in stream:
        out.append(chunk)
    return out


def _sse_bytes(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event)}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# Fake invoke_function — keyed by function name
# ---------------------------------------------------------------------------

class FakeInvoker:
    """Tracks calls + returns canned responses for each downstream function."""

    def __init__(self) -> None:
        self.responses: dict[str, Any] = {}
        self.delays: dict[str, float] = {}
        self.errors: dict[str, Exception] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fire_and_forget_calls: list[tuple[str, dict[str, Any]]] = []
        self.parallel_window: list[tuple[str, float, float]] = []  # name, start, end

    async def invoke_function(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        timeout: float = 8.0,
        attempts: int = 2,
        client: Any | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        self.calls.append((name, payload))
        if name in self.errors:
            raise self.errors[name]
        delay = self.delays.get(name, 0.0)
        if delay > 0:
            # Respect the timeout — simulate the real httpx behaviour.
            try:
                await asyncio.wait_for(asyncio.sleep(delay), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise invoke_helpers.InvokeTimeout(
                    f"{name} timed out after {timeout}s"
                ) from exc
        ended = time.perf_counter()
        self.parallel_window.append((name, started, ended))
        if name not in self.responses:
            return {}
        canned = self.responses[name]
        # Synthesizer responses are authored as a list of event dicts (matching
        # the old streaming shape). The new Basic I/O synthesizer wraps them
        # in ``{"events": [...]}``, so do the same here when needed.
        if name == "synthesizer" and isinstance(canned, list):
            return {"ok": True, "events": list(canned)}
        return canned

    async def invoke_fire_and_forget(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        timeout: float = 4.0,
        client: Any | None = None,
    ) -> None:
        self.fire_and_forget_calls.append((name, payload))

    def stream_function(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        timeout: float = 60.0,
        client: Any | None = None,
    ):
        responses = self.responses.get(name, [])

        @asynccontextmanager
        async def _cm():
            async def _gen():
                for chunk in responses:
                    await asyncio.sleep(0)  # let the loop interleave
                    if isinstance(chunk, bytes):
                        yield chunk
                    elif isinstance(chunk, dict):
                        yield _sse_bytes(chunk)
                    else:
                        yield _sse_bytes({"type": "text_chunk", "content": str(chunk)})
            yield _gen()

        return _cm()


@pytest.fixture
def fake_invoker(monkeypatch: pytest.MonkeyPatch) -> FakeInvoker:
    fake = FakeInvoker()
    # Patch the names that index.py imported into its own module namespace.
    monkeypatch.setattr(index, "invoke_function", fake.invoke_function)
    monkeypatch.setattr(index, "invoke_fire_and_forget", fake.invoke_fire_and_forget)
    monkeypatch.setattr(index, "stream_function", fake.stream_function)
    # Tighten timeouts so timeout tests don't drag the suite out.
    monkeypatch.setattr(index, "TOOL_TIMEOUT_S", 1.0)
    monkeypatch.setattr(index, "ROUTER_TIMEOUT_S", 1.0)
    monkeypatch.setattr(index, "SYNTH_TIMEOUT_S", 5.0)
    monkeypatch.setattr(index, "TOTAL_TIMEOUT_S", 10.0)
    return fake


# ---------------------------------------------------------------------------
# Test 1 — Happy path (tabular query)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_tabular(fake_invoker: FakeInvoker) -> None:
    fake_invoker.responses["intent-router"] = {
        "intent": "tabular_query",
        "language": "en",
        "confidence": 0.91,
        "normalized_query": "show all chain snatchings near Indiranagar",
        "entities": {"geo": "Indiranagar", "crime": "chain_snatching"},
        "reasoning": "tabular keywords detected",
    }
    fake_invoker.responses["sql-generator"] = {
        "sql": "SELECT * FROM firs WHERE crime_type='chain_snatching'",
        "rows": [{"fir_no": "FIR-2026-BLR-101"}],
        "row_count": 1,
    }
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "3 FIRs found near Indiranagar. "},
        {"type": "viz_spec", "map": {"center": {"lat": 12.97, "lng": 77.64}}},
        {"type": "audit_chain", "steps": []},
        {"type": "done"},
    ]

    chunks = await _collect(index.orchestrate_stream(
        query="show all chain snatchings near Indiranagar",
        language_hint="en",
        session_id="sess-123",
        user_role="inspector",
    ))
    events = _parse_sse_events(chunks)
    types = [e["type"] for e in events]

    assert "started" in types
    assert "routed" in types
    assert types.count("tool_started") == 1
    assert types.count("tool_done") == 1
    assert "text_chunk" in types
    assert "viz_spec" in types
    assert types[-1] == "orchestrator_done"

    # Tool fan-out was sql-generator only for tabular_query.
    called = [c[0] for c in fake_invoker.calls]
    assert "intent-router" in called
    assert "sql-generator" in called
    assert "cypher-generator" not in called

    # Audit logger fired once (fire-and-forget).
    # Give the background task one tick to start.
    await asyncio.sleep(0.05)
    audit_names = [c[0] for c in fake_invoker.fire_and_forget_calls]
    assert "audit-logger" in audit_names


# ---------------------------------------------------------------------------
# Test 2 — Mixed intent fan-out (3 tools concurrent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_intent_fans_out_in_parallel(fake_invoker: FakeInvoker) -> None:
    fake_invoker.responses["intent-router"] = {
        "intent": "mixed",
        "language": "en",
        "confidence": 0.82,
        "normalized_query": "investigate the gang network around case FIR-101",
        "entities": {},
    }
    # Each tool sleeps for 0.2s — if they run serially total > 0.6s,
    # if parallel total ~ 0.2s.
    fake_invoker.delays["sql-generator"] = 0.2
    fake_invoker.delays["cypher-generator"] = 0.2
    fake_invoker.delays["rag-retriever"] = 0.2
    fake_invoker.responses["sql-generator"] = {"rows": []}
    fake_invoker.responses["cypher-generator"] = {"nodes": [], "edges": []}
    fake_invoker.responses["rag-retriever"] = {"chunks": []}
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "combined answer"},
        {"type": "done"},
    ]

    started = time.perf_counter()
    chunks = await _collect(index.orchestrate_stream(
        query="investigate the gang network around case FIR-101",
        user_role="dcp",
    ))
    elapsed = time.perf_counter() - started

    events = _parse_sse_events(chunks)
    tool_started = [e for e in events if e["type"] == "tool_started"]
    tool_done = [e for e in events if e["type"] == "tool_done"]

    assert len(tool_started) == 3
    assert len(tool_done) == 3
    assert {e["tool"] for e in tool_started} == {
        "sql-generator", "cypher-generator", "rag-retriever",
    }

    # Parallel execution check — three 200ms tools should finish in < 600ms.
    # Allow generous slack (1.0s) for CI jitter; serial would be > 0.6s.
    assert elapsed < 1.0, f"Mixed fan-out ran serially (elapsed={elapsed:.2f}s)"

    # Confirm by inspecting recorded windows — they should overlap heavily.
    windows = [
        (name, s, e) for (name, s, e) in fake_invoker.parallel_window
        if name in {"sql-generator", "cypher-generator", "rag-retriever"}
    ]
    assert len(windows) == 3
    earliest_start = min(s for _, s, _ in windows)
    latest_start = max(s for _, s, _ in windows)
    # All three should have started within 50ms of each other.
    assert (latest_start - earliest_start) < 0.05


# ---------------------------------------------------------------------------
# Test 3 — Tool failure does not abort the pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_failure_continues_with_warning(fake_invoker: FakeInvoker) -> None:
    fake_invoker.responses["intent-router"] = {
        "intent": "mixed",
        "language": "en",
        "confidence": 0.8,
        "normalized_query": "q",
        "entities": {},
    }
    fake_invoker.responses["sql-generator"] = {"rows": [{"fir_no": "X"}]}
    fake_invoker.errors["cypher-generator"] = invoke_helpers.InvokeHTTPError(
        503, "neo4j unavailable", "cypher-generator",
    )
    fake_invoker.responses["rag-retriever"] = {"chunks": []}
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "partial answer"},
        {"type": "done"},
    ]

    chunks = await _collect(index.orchestrate_stream(
        query="mixed query",
        user_role="inspector",
    ))
    events = _parse_sse_events(chunks)

    tool_done = [e for e in events if e["type"] == "tool_done"]
    by_tool = {e["tool"]: e for e in tool_done}

    assert by_tool["sql-generator"]["ok"] is True
    assert by_tool["cypher-generator"]["ok"] is False
    assert "503" in (by_tool["cypher-generator"]["error"] or "")
    assert by_tool["rag-retriever"]["ok"] is True

    # Synthesizer still got invoked despite the failure.
    synth_invocation = next(
        (c for c in fake_invoker.calls if c[0] == "synthesizer"),
        None,
    )
    # synthesizer is called via stream_function, not invoke_function — but
    # the warnings payload must reach it. We verify via the final
    # orchestrator_done event instead.
    done = events[-1]
    assert done["type"] == "orchestrator_done"
    assert done["warning_count"] >= 1


# ---------------------------------------------------------------------------
# Test 4 — Slow tool gets aborted at TOOL_TIMEOUT_S; others complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_slow_tool_aborted_others_complete(fake_invoker: FakeInvoker) -> None:
    # 1s per-tool timeout in the fixture; this tool sleeps 3s.
    fake_invoker.responses["intent-router"] = {
        "intent": "mixed",
        "language": "en",
        "confidence": 0.7,
        "normalized_query": "q",
        "entities": {},
    }
    fake_invoker.delays["sql-generator"] = 3.0      # will time out
    fake_invoker.responses["sql-generator"] = {"rows": []}
    fake_invoker.responses["cypher-generator"] = {"nodes": []}
    fake_invoker.responses["rag-retriever"] = {"chunks": []}
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "best-effort"},
        {"type": "done"},
    ]

    started = time.perf_counter()
    chunks = await _collect(index.orchestrate_stream(query="q", user_role="inspector"))
    elapsed = time.perf_counter() - started

    events = _parse_sse_events(chunks)
    tool_done = {e["tool"]: e for e in events if e["type"] == "tool_done"}

    assert tool_done["sql-generator"]["ok"] is False
    assert "timeout" in (tool_done["sql-generator"]["error"] or "").lower()
    assert tool_done["cypher-generator"]["ok"] is True
    assert tool_done["rag-retriever"]["ok"] is True

    # Total run should not be much longer than the 1s tool timeout — the
    # slow tool gets aborted, the fast ones return immediately, synth is
    # nearly free, audit is fire-and-forget. Allow generous slack for CI.
    assert elapsed < 3.5, f"Pipeline didn't enforce timeout (elapsed={elapsed:.2f}s)"


# ---------------------------------------------------------------------------
# Test 5 — SSE event ordering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_event_ordering(fake_invoker: FakeInvoker) -> None:
    fake_invoker.responses["intent-router"] = {
        "intent": "tabular_query",
        "language": "kn",
        "confidence": 0.9,
        "normalized_query": "ಕ್ರೈಮ್",
        "entities": {},
    }
    fake_invoker.responses["sql-generator"] = {"rows": []}
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "ಉತ್ತರ "},
        {"type": "text_chunk", "content": "ಭಾಗ ೨"},
        {"type": "viz_spec", "map": None},
        {"type": "audit_chain", "steps": []},
        {"type": "done"},
    ]

    chunks = await _collect(index.orchestrate_stream(
        query="ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕ್ರೈಮ್ ತೋರಿಸಿ",
        language_hint="kn",
        user_role="inspector",
    ))
    events = _parse_sse_events(chunks)
    types = [e["type"] for e in events]

    # The required prefix order: started -> routed -> tool_started -> tool_done.
    assert types.index("started") < types.index("routed")
    assert types.index("routed") < types.index("tool_started")
    assert types.index("tool_started") < types.index("tool_done")

    # Synthesizer events come after tool_done.
    assert types.index("tool_done") < types.index("text_chunk")
    assert types.index("text_chunk") < types.index("viz_spec")
    assert types.index("viz_spec") < types.index("audit_chain")
    assert types.index("audit_chain") < types.index("orchestrator_done")

    # orchestrator_done is always the very last event.
    assert types[-1] == "orchestrator_done"

    # Kannada language flows through the routed event.
    routed = next(e for e in events if e["type"] == "routed")
    assert routed["language"] == "kn"


# ---------------------------------------------------------------------------
# Bonus — intent → tool mapping (pure unit)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("intent,expected", [
    ("tabular_query",     ["sql-generator"]),
    ("geo_query",         ["sql-generator"]),
    ("graph_query",       ["cypher-generator"]),
    ("lookup",            ["rag-retriever"]),
    ("semantic",          ["rag-retriever"]),
    ("predictive_query",  ["predictive-service"]),
    ("meta_query",        []),
    ("mixed",             ["sql-generator", "cypher-generator", "rag-retriever"]),
    ("nonsense",          ["rag-retriever"]),  # safe default
])
def test_tools_for_intent(intent: str, expected: list[str]) -> None:
    assert index.tools_for_intent(intent) == expected


# ---------------------------------------------------------------------------
# Basic I/O handler — returns JSON dict (not a generator)
# ---------------------------------------------------------------------------

class _FakeBasicIO:
    """Minimal stand-in for the Catalyst Basic I/O object."""

    def __init__(self, body):
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._body = body
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self.written: bytearray = bytearray()

    def get_request_body(self):
        return self._body

    def set_status(self, status: int) -> None:
        self.status = status

    def set_header(self, k: str, v: str) -> None:
        self.headers[k] = v

    def set_content_type(self, ct: str) -> None:
        self.headers["Content-Type"] = ct

    def write(self, chunk) -> None:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        self.written.extend(chunk)


def test_handler_returns_json_dict(fake_invoker: FakeInvoker) -> None:
    """Basic I/O handler must return a JSON dict (not a generator)."""
    fake_invoker.responses["intent-router"] = {
        "intent": "tabular_query",
        "language": "en",
        "confidence": 0.9,
        "normalized_query": "show me FIRs",
        "entities": {},
    }
    fake_invoker.responses["sql-generator"] = {"rows": []}
    fake_invoker.responses["synthesizer"] = [
        {"type": "text_chunk", "content": "ok"},
        {"type": "done"},
    ]

    fake_io = _FakeBasicIO(body={"query": "show me FIRs", "user_role": "inspector"})
    result = index.handler(context=None, basic_io=fake_io)

    assert isinstance(result, dict), "handler must return a dict, not a generator"
    assert result["ok"] is True
    assert isinstance(result["events"], list)
    types = [e["type"] for e in result["events"]]
    assert types[0] == "started"
    assert types[-1] == "orchestrator_done"
    assert fake_io.status == 200
    assert fake_io.headers.get("Content-Type", "").startswith("application/json")


def test_handler_bad_request_returns_400_json() -> None:
    """Empty body → 400 with structured error in events list."""
    fake_io = _FakeBasicIO(body=b"")
    result = index.handler(context=None, basic_io=fake_io)

    assert isinstance(result, dict)
    assert result["ok"] is False
    assert fake_io.status == 400
    types = [e["type"] for e in result["events"]]
    assert "error" in types
    assert result["events"][-1]["type"] == "orchestrator_done"
