"""Pytest suite for the synthesizer Catalyst Function.

Covers:
  * SSE shape for an English tabular query
  * viz_spec containing map markers is emitted
  * audit_chain enumerates router → tool_call(s) → synthesizer
  * Kannada query routes to Gemini and answer is in Kannada
  * English routine query routes to Qwen and answer is in English
  * Bad request body returns a structured SSE error

The LLM backends (``_stream_qwen``, ``_stream_gemini``) are monkeypatched
so the tests run hermetically — no network, no credentials needed.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable

import pytest

# Make this directory importable as a package-less module set.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import index  # noqa: E402  — module under test
from index import SynthRequest, synthesize_stream, handler  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ENGLISH_VIZ = (
    "<viz>"
    '{"map":{"center":{"lat":12.9719,"lng":77.6412},"zoom":15,'
    '"markers":[{"id":"FIR-2026-BLR-101","lat":12.9719,"lng":77.6412,'
    '"label":"22 May","severity":"med"}],"heatmap":null},'
    '"graph":null,"chart":null}'
    "</viz>"
)

KANNADA_VIZ = (
    "<viz>"
    '{"map":{"center":{"lat":12.97,"lng":77.64},"zoom":14,"markers":[],'
    '"heatmap":null},"graph":null,"chart":null}'
    "</viz>"
)


def _english_chunks() -> Iterable[str]:
    yield "3 chain-snatching FIRs were registered near Indiranagar metro. "
    yield "Two were filed at Indiranagar PS [FIR-2026-BLR-101]. "
    yield "Recommend a joint review across neighbouring stations.\n\n"
    yield ENGLISH_VIZ


def _kannada_chunks() -> Iterable[str]:
    yield "ಕಳೆದ 30 ದಿನಗಳಲ್ಲಿ ಇಂದಿರಾನಗರ ಬಳಿ 2 ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ. "
    yield "ಎರಡೂ ಇಂದಿರಾನಗರ ಠಾಣೆಯಲ್ಲಿ [FIR-2026-BLR-118].\n\n"
    yield KANNADA_VIZ


@pytest.fixture
def english_payload() -> dict:
    return {
        "request_id": "req_eng_001",
        "query": "How many chain snatchings near Indiranagar metro last 30 days?",
        "language": "en",
        "user_id": "psi_test_1",
        "role": "sub_inspector",
        "router_decision": {
            "intent": "tabular_geo",
            "confidence": 0.92,
            "model": "qwen2.5-7b-instruct",
            "complexity": "low",
        },
        "tool_results": [
            {
                "tool": "sql",
                "latency_ms": 220,
                "rows": [
                    {"fir_no": "FIR-2026-BLR-101", "station": "Indiranagar PS",
                     "date": "2026-05-22", "lat": 12.9719, "lng": 77.6412},
                    {"fir_no": "FIR-2026-BLR-118", "station": "Indiranagar PS",
                     "date": "2026-06-02", "lat": 12.9722, "lng": 77.6398},
                ],
            },
        ],
    }


@pytest.fixture
def kannada_payload() -> dict:
    return {
        "request_id": "req_kn_001",
        "query": "ಕಳೆದ 30 ದಿನಗಳಲ್ಲಿ ಇಂದಿರಾನಗರ ಬಳಿ ಎಷ್ಟು ಚೈನ್ ಸ್ನಾಚಿಂಗ್?",
        "language": "kn",
        "user_id": "psi_test_2",
        "role": "sub_inspector",
        "router_decision": {"intent": "tabular_geo", "confidence": 0.88,
                            "complexity": "low"},
        "tool_results": [
            {
                "tool": "sql",
                "latency_ms": 240,
                "rows": [
                    {"fir_no": "FIR-2026-BLR-118", "station": "ಇಂದಿರಾನಗರ PS",
                     "date": "2026-06-02", "lat": 12.9722, "lng": 77.6398},
                ],
            },
        ],
    }


@pytest.fixture(autouse=True)
def _mute_audit(monkeypatch):
    """Never touch real Catalyst NoSQL during tests."""
    monkeypatch.setattr(index, "_write_audit", lambda entry: None)
    monkeypatch.setattr(index, "_write_audit_async", lambda entry: None)


class _FakeBasicIO:
    """Minimal stand-in for the Catalyst Advanced I/O object."""

    def __init__(self, body: bytes | str | dict | None) -> None:
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._body = body
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self.written: bytearray = bytearray()

    # Catalyst-shaped read helpers
    def get_request_body(self):
        return self._body

    def set_status(self, status: int) -> None:
        self.status = status

    def set_header(self, k: str, v: str) -> None:
        self.headers[k] = v


def _decode_sse(stream: Iterable[bytes]) -> list[dict]:
    events: list[dict] = []
    for raw in stream:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            events.append(json.loads(payload))
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_english_routes_to_qwen(monkeypatch, english_payload):
    qwen_calls: list[str] = []
    gemini_calls: list[str] = []

    def fake_qwen(prompt, system, *, model):
        qwen_calls.append(model)
        return _english_chunks()

    def fake_gemini(prompt, system, *, model):
        gemini_calls.append(model)
        return iter([])

    monkeypatch.setattr(index, "_stream_qwen", fake_qwen)
    monkeypatch.setattr(index, "_stream_gemini", fake_gemini)

    req = SynthRequest.from_payload(english_payload)
    events = _decode_sse(synthesize_stream(req))

    assert qwen_calls, "English routine query should route to Qwen"
    assert not gemini_calls, "English routine query must NOT call Gemini"

    text_events = [e for e in events if e["type"] == "text_chunk"]
    assert text_events, "expected at least one text_chunk"
    joined = "".join(e["content"] for e in text_events)
    assert "chain-snatching" in joined
    # English query should yield English answer text.
    assert "ಪ್ರಕರಣ" not in joined  # no Kannada words leak through


def test_viz_spec_carries_map_markers(monkeypatch, english_payload):
    monkeypatch.setattr(index, "_stream_qwen",
                        lambda p, s, *, model: _english_chunks())

    req = SynthRequest.from_payload(english_payload)
    events = _decode_sse(synthesize_stream(req))

    viz_events = [e for e in events if e["type"] == "viz_spec"]
    assert len(viz_events) == 1, "exactly one viz_spec event"
    viz = viz_events[0]
    assert viz["map"] is not None
    assert viz["map"]["zoom"] == 15
    markers = viz["map"]["markers"]
    assert markers and markers[0]["id"] == "FIR-2026-BLR-101"
    assert viz["graph"] is None
    assert viz["chart"] is None


def test_audit_chain_has_all_steps(monkeypatch, english_payload):
    monkeypatch.setattr(index, "_stream_qwen",
                        lambda p, s, *, model: _english_chunks())

    req = SynthRequest.from_payload(english_payload)
    events = _decode_sse(synthesize_stream(req))

    audit_events = [e for e in events if e["type"] == "audit_chain"]
    assert len(audit_events) == 1
    steps = audit_events[0]["steps"]
    step_names = [s["step"] for s in steps]
    assert step_names[0] == "intent_router"
    assert "tool_call" in step_names
    assert step_names[-1] == "synthesizer"

    synth_step = steps[-1]
    assert synth_step["model_family"] == "qwen"
    assert "FIR-2026-BLR-101" in synth_step["sources"]
    assert "FIR-2026-BLR-118" in synth_step["sources"]


def test_kannada_routes_to_gemini(monkeypatch, kannada_payload):
    qwen_calls: list[str] = []
    gemini_calls: list[str] = []

    def fake_qwen(prompt, system, *, model):
        qwen_calls.append(model)
        return iter([])

    def fake_gemini(prompt, system, *, model):
        gemini_calls.append(model)
        return _kannada_chunks()

    monkeypatch.setattr(index, "_stream_qwen", fake_qwen)
    monkeypatch.setattr(index, "_stream_gemini", fake_gemini)

    req = SynthRequest.from_payload(kannada_payload)
    events = _decode_sse(synthesize_stream(req))

    assert gemini_calls, "Kannada query must route to Gemini 2.5 Pro"
    assert not qwen_calls, "Kannada query must NOT call Qwen"

    text_events = [e for e in events if e["type"] == "text_chunk"]
    joined = "".join(e["content"] for e in text_events)
    assert "ಪ್ರಕರಣ" in joined or "ಠಾಣೆ" in joined, \
        "Kannada query should produce Kannada-script answer"

    audit = next(e for e in events if e["type"] == "audit_chain")
    assert audit["steps"][-1]["model_family"] == "gemini"
    assert audit["steps"][-1]["language"] == "kn"


def test_done_event_always_terminates_stream(monkeypatch, english_payload):
    monkeypatch.setattr(index, "_stream_qwen",
                        lambda p, s, *, model: _english_chunks())
    req = SynthRequest.from_payload(english_payload)
    events = _decode_sse(synthesize_stream(req))
    assert events[-1]["type"] == "done"
    assert events[-1]["latency_ms"] >= 0


def test_complex_routes_to_gemini_even_in_english(monkeypatch, english_payload):
    """A high-complexity multi-intent query must promote to Gemini 2.5 Pro."""
    english_payload["router_decision"]["complexity"] = "high"
    english_payload["router_decision"]["intent"] = "mixed"
    english_payload["router_decision"]["intents"] = ["tabular_geo", "graph_query",
                                                      "predictive_query"]

    gemini_calls: list[str] = []
    qwen_calls: list[str] = []
    monkeypatch.setattr(index, "_stream_qwen",
                        lambda p, s, *, model: (qwen_calls.append(model) or iter([])))
    monkeypatch.setattr(index, "_stream_gemini",
                        lambda p, s, *, model: (gemini_calls.append(model)
                                                or _english_chunks()))

    req = SynthRequest.from_payload(english_payload)
    events = _decode_sse(synthesize_stream(req))
    assert gemini_calls and not qwen_calls
    assert events[-1]["type"] == "done"


def test_bad_request_returns_sse_error(monkeypatch):
    fake_io = _FakeBasicIO(body=b"")  # empty -> ValueError
    out = b"".join(handler(context=None, basic_io=fake_io))
    decoded = _decode_sse([out])
    assert decoded[0]["type"] == "error"
    assert decoded[0]["code"] == "bad_request"
    assert decoded[-1]["type"] == "done"
    assert fake_io.status == 400


def test_full_handler_smoke(monkeypatch, english_payload):
    """End-to-end through ``handler`` — confirms SSE headers + stream."""
    monkeypatch.setattr(index, "_stream_qwen",
                        lambda p, s, *, model: _english_chunks())

    fake_io = _FakeBasicIO(body=english_payload)
    chunks = list(handler(context=None, basic_io=fake_io))
    # _write_response will preferentially call basic_io.write; assert that
    # everything we expect to send made it through one of the channels.
    if fake_io.written:
        data = bytes(fake_io.written)
    else:
        data = b"".join(chunks)
    events = _decode_sse([data])

    types_seen = {e["type"] for e in events}
    assert "text_chunk" in types_seen
    assert "viz_spec" in types_seen
    assert "audit_chain" in types_seen
    assert events[-1]["type"] == "done"
    assert fake_io.status == 200
    assert fake_io.headers.get("Content-Type", "").startswith("text/event-stream")
