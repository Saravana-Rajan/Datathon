"""End-to-end happy-path query tests for the Sarvik orchestrator.

These tests POST a real query to the deployed Catalyst orchestrator
function and consume the SSE stream it returns. They only run when
``CATALYST_API_BASE`` is set (e.g. in the deploy branch CI matrix) — in
all other contexts they auto-skip via the ``integration_base_url``
fixture.

The orchestrator contract is documented in
``app/backend/functions/orchestrator/index.py``:

    POST {API_BASE}/server/orchestrator
    body: { "query": str, "language_hint": "en|kn|auto",
            "session_id": str, "user_role": str }
    response: text/event-stream of JSON events

Event types we assert on:
    started, routed, tool_started, tool_done,
    text_chunk, viz_spec, audit_chain, done, orchestrator_done

We use ``httpx.AsyncClient.stream`` to read SSE chunks incrementally so
slow tools don't time out the test.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, AsyncIterator

import httpx
import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------

async def _stream_events(
    base_url: str,
    query: str,
    *,
    language_hint: str = "auto",
    user_role: str = "inspector",
    session_id: str = "test-e2e",
    timeout: float = 30.0,
) -> AsyncIterator[dict[str, Any]]:
    """POST to the orchestrator and yield each parsed SSE event."""
    url = f"{base_url}/server/orchestrator"
    payload = {
        "query": query,
        "language_hint": language_hint,
        "session_id": session_id,
        "user_role": user_role,
    }
    headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
    auth_token = os.getenv("CATALYST_AUTH_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            buffer = b""
            async for chunk in resp.aiter_bytes():
                buffer += chunk
                while b"\n\n" in buffer:
                    raw_event, buffer = buffer.split(b"\n\n", 1)
                    for line in raw_event.split(b"\n"):
                        if line.startswith(b"data:"):
                            payload_str = line[5:].decode("utf-8").strip()
                            if not payload_str:
                                continue
                            try:
                                yield json.loads(payload_str)
                            except json.JSONDecodeError:
                                # Be lenient — orchestrator currently emits
                                # only valid JSON but we don't want a single
                                # malformed event to fail the whole suite.
                                continue


async def _collect_events(
    base_url: str, query: str, **kwargs: Any,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    async for event in _stream_events(base_url, query, **kwargs):
        out.append(event)
        # Defensive guard: stop once orchestrator_done arrives even if the
        # server keeps the connection open by mistake.
        if event.get("type") == "orchestrator_done":
            break
    return out


def _types(events: list[dict[str, Any]]) -> list[str]:
    return [e.get("type") for e in events]


# ---------------------------------------------------------------------------
# Test 1 — English tabular query → map markers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_english_tabular_geo_returns_map_markers(
    integration_base_url: str,
) -> None:
    """English geo query should route to sql-generator and produce a map viz."""
    events = await _collect_events(
        integration_base_url,
        "Show all chain snatching cases near Indiranagar metro in the last 30 days",
        language_hint="en",
        user_role="inspector",
    )

    types = _types(events)
    assert "started" in types, f"missing 'started' event: {types}"
    assert "routed" in types, f"missing 'routed' event: {types}"
    assert types[-1] == "orchestrator_done", f"last event: {types[-1]}"

    routed = next(e for e in events if e["type"] == "routed")
    assert routed.get("language") == "en"
    assert routed.get("intent") in {"geo_query", "tabular_query"}

    # sql-generator should have been the tool invoked.
    tool_done = [e for e in events if e["type"] == "tool_done"]
    tools_called = {e["tool"] for e in tool_done}
    assert "sql-generator" in tools_called, (
        f"expected sql-generator in {tools_called}"
    )

    # Map viz_spec must arrive — the frontend renders markers from it.
    viz_specs = [e for e in events if e["type"] == "viz_spec"]
    assert viz_specs, "no viz_spec event returned"
    # Look for a map-shaped payload in at least one spec.
    has_map = any(
        ("map" in spec) or ("markers" in spec) or (spec.get("viz_type") == "map")
        for spec in viz_specs
    )
    assert has_map, f"no map markers in viz_spec payloads: {viz_specs!r}"


# ---------------------------------------------------------------------------
# Test 2 — Kannada graph query → network nodes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kannada_graph_query_returns_network(
    integration_base_url: str,
    lang_helpers: dict,
) -> None:
    """Kannada query about a criminal network should route to cypher-generator."""
    events = await _collect_events(
        integration_base_url,
        "ಆರೋಪಿ ಅಹ್ಮದ್ ನಾಯಕ್ ಸುತ್ತಲಿನ ಅಪರಾಧ ಜಾಲವನ್ನು ತೋರಿಸಿ",
        language_hint="kn",
        user_role="dcp",
    )

    types = _types(events)
    assert "routed" in types
    assert types[-1] == "orchestrator_done"

    routed = next(e for e in events if e["type"] == "routed")
    assert routed["language"] == "kn"
    assert routed["intent"] == "graph_query"

    # cypher-generator must be invoked for graph_query.
    tools = {e["tool"] for e in events if e["type"] == "tool_done"}
    assert "cypher-generator" in tools, f"expected cypher-generator in {tools}"

    # Network viz with nodes + edges.
    viz_specs = [e for e in events if e["type"] == "viz_spec"]
    assert viz_specs, "no viz_spec event returned"
    has_network = any(
        ("nodes" in spec and "edges" in spec) or spec.get("viz_type") == "network"
        for spec in viz_specs
    )
    assert has_network, f"no network nodes/edges in viz_specs: {viz_specs!r}"

    # Synthesized text should be in Kannada.
    text_chunks = "".join(
        e.get("content", "") for e in events if e.get("type") == "text_chunk"
    )
    assert lang_helpers["has_kannada"](text_chunks), (
        f"Expected Kannada Unicode in answer; got: {text_chunks[:200]!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 — Predictive query → forecast with confidence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_predictive_query_returns_forecast_with_confidence(
    integration_base_url: str,
) -> None:
    """Predictive routing should hit predictive-service and emit a confidence band."""
    events = await _collect_events(
        integration_base_url,
        "Forecast vehicle theft hotspots for next week across Mysuru district",
        language_hint="en",
        user_role="dcp",
    )

    types = _types(events)
    assert "routed" in types
    assert types[-1] == "orchestrator_done"

    routed = next(e for e in events if e["type"] == "routed")
    assert routed["intent"] == "predictive_query"

    tools = {e["tool"] for e in events if e["type"] == "tool_done"}
    assert "predictive-service" in tools

    # The synthesizer must surface a confidence indicator somewhere.
    # We accept either an explicit numeric field in viz_spec OR an inline
    # phrase like "85% confidence" in the text chunks.
    viz_specs = [e for e in events if e["type"] == "viz_spec"]
    text = "".join(e.get("content", "") for e in events if e["type"] == "text_chunk")

    has_numeric_conf = any(
        any(k in spec for k in ("confidence", "confidence_interval", "ci"))
        for spec in viz_specs
    )
    has_text_conf = bool(re.search(r"\b\d{1,3}\s*%\s*(confidence|ci)\b", text, re.I))
    assert has_numeric_conf or has_text_conf, (
        f"forecast missing confidence: viz_specs={viz_specs!r} text={text[:200]!r}"
    )

    # Predictive results must never be framed as Minority Report — sanity
    # check that we don't surface arrest/pre-crime language (locked
    # ethics constraint from design.md §16).
    forbidden = ("pre-crime", "precrime", "arrest probability",
                 "will commit", "guaranteed to offend")
    lowered = text.lower()
    for term in forbidden:
        assert term not in lowered, f"forecast leaked forbidden phrase {term!r}"


# ---------------------------------------------------------------------------
# Test 4 — "Why?" follow-up returns audit chain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_why_follow_up_returns_audit_chain(
    integration_base_url: str,
) -> None:
    """A meta_query should surface the audit chain for the prior turn."""
    session_id = "test-audit-followup-001"

    # Turn 1 — set up something to ask "why" about.
    _ = await _collect_events(
        integration_base_url,
        "Show burglary FIRs in MG Road Police Station for 2025",
        language_hint="en",
        user_role="inspector",
        session_id=session_id,
    )

    # Turn 2 — the meta query.
    events = await _collect_events(
        integration_base_url,
        "Why did you choose those FIRs?",
        language_hint="en",
        user_role="inspector",
        session_id=session_id,
    )

    types = _types(events)
    assert "routed" in types
    assert types[-1] == "orchestrator_done"

    routed = next(e for e in events if e["type"] == "routed")
    assert routed["intent"] == "meta_query"

    # The synthesizer should emit an audit_chain event.
    chains = [e for e in events if e["type"] == "audit_chain"]
    assert chains, f"no audit_chain event in {types}"

    chain_payload = chains[0]
    steps = chain_payload.get("steps") or chain_payload.get("chain") or []
    assert isinstance(steps, list), f"chain steps not a list: {chain_payload!r}"
    assert len(steps) >= 1, "audit chain returned empty"

    # Every step must carry a step_type or stage so the UI can render it.
    for step in steps:
        assert isinstance(step, dict), f"step not a dict: {step!r}"
        assert any(k in step for k in ("step_type", "stage", "type")), (
            f"step missing type marker: {step!r}"
        )
