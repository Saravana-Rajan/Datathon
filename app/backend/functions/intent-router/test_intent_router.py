"""Unit tests for the KSP Saathi intent-router function.

Run from the project root:
    cd app/backend/functions/intent-router
    pytest test_intent_router.py -v

Or from anywhere:
    pytest app/backend/functions/intent-router/test_intent_router.py -v

All LLM calls are mocked — no network traffic. We also stub the audit-log
write so tests don't depend on the Catalyst SDK being installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Make the function module + shared package importable
_HERE = Path(__file__).resolve().parent
_BACKEND_ROOT = _HERE.parent.parent
for _p in (_BACKEND_ROOT, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import index  # noqa: E402  — module under test


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _silence_audit_log(monkeypatch):
    """No-op the audit logger so tests don't try to write to NoSQL."""
    monkeypatch.setattr(
        index.catalyst_client,
        "log_audit",
        lambda *a, **kw: "test-request-id",
    )


def _mock_llm(response_dict: dict[str, Any]):
    """Build a context manager that patches the QuickML chat to return a JSON
    string matching `response_dict`. Disables Gemini fallback too so we
    don't accidentally fall through.
    """
    raw = json.dumps(response_dict, ensure_ascii=False)
    return patch.object(
        index.catalyst_client,
        "quickml_chat",
        return_value=raw,
    )


def _build_request(query: str, **overrides) -> index.RouterRequest:
    payload = {
        "query": query,
        "language_hint": "auto",
        "session_id": "sess-test",
        "user_role": "inspector",
        **overrides,
    }
    return index.RouterRequest(**payload)


# ---------------------------------------------------------------------------
# Required test cases from the spec
# ---------------------------------------------------------------------------

def test_english_tabular():
    """'Show me thefts last month' -> tabular_query, language=en"""
    llm_resp = {
        "intent": "tabular_query",
        "entities": {"crime_type": "theft", "time_range": "last month"},
        "confidence": 0.95,
        "reasoning": "Counts/filters by crime_type and date range.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("Show me thefts last month"))

    assert out.intent == "tabular_query"
    assert out.language == "en"
    assert out.confidence >= 0.9
    assert out.entities.get("crime_type") == "theft"
    assert out.request_id  # uuid was generated
    assert out.router_latency_ms >= 0


def test_kannada_geo():
    """Kannada 'where' question -> geo_query, language=kn"""
    query = "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕಳ್ಳತನ ಎಲ್ಲಿ ಹೆಚ್ಚು?"
    llm_resp = {
        "intent": "geo_query",
        "entities": {
            "crime_type": "theft",
            "location": "Bengaluru",
            "modifier": "where_hotspot",
        },
        "confidence": 0.93,
        "reasoning": "Kannada 'where' + 'most' => hotspot detection.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request(query))

    assert out.intent == "geo_query"
    assert out.language == "kn"  # auto-detected via Kannada Unicode block
    assert out.confidence >= 0.9


def test_graph_query():
    """Network / connection query -> graph_query"""
    llm_resp = {
        "intent": "graph_query",
        "entities": {"person_name": "Ravi Kumar", "traversal": "neighbors_1_hop"},
        "confidence": 0.96,
        "reasoning": "Relationship traversal -> Cypher.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("Who is connected to Ravi Kumar"))

    assert out.intent == "graph_query"
    assert out.language == "en"
    assert out.entities.get("person_name") == "Ravi Kumar"


def test_predictive_query():
    """Future-tense forecast -> predictive_query"""
    llm_resp = {
        "intent": "predictive_query",
        "entities": {"crime_type": "robbery", "horizon": "next_week"},
        "confidence": 0.92,
        "reasoning": "Future tense + horizon => Zia AutoML.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("Will robberies increase next week"))

    assert out.intent == "predictive_query"
    assert out.entities.get("horizon") == "next_week"


def test_meta_query():
    """'Why did you say that' -> meta_query (audit-log lookup)"""
    llm_resp = {
        "intent": "meta_query",
        "entities": {"target": "previous_answer"},
        "confidence": 0.99,
        "reasoning": "Self-referential question about previous turn.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("Why did you say that"))

    assert out.intent == "meta_query"
    assert out.confidence >= 0.95


def test_mixed_multi_tool():
    """Composite query touching tabular + predictive -> mixed"""
    llm_resp = {
        "intent": "mixed",
        "entities": {
            "crime_type": "theft",
            "location": "MG Road",
            "horizon": "next_week",
            "sub_intents": ["tabular_query", "predictive_query"],
        },
        "confidence": 0.90,
        "reasoning": "Historic table + forward forecast.",
    }
    query = "Show MG Road thefts and predict next week"
    with _mock_llm(llm_resp):
        out = index.route(_build_request(query))

    assert out.intent == "mixed"
    assert set(out.entities.get("sub_intents", [])) == {
        "tabular_query",
        "predictive_query",
    }


# ---------------------------------------------------------------------------
# Edge-case / robustness tests
# ---------------------------------------------------------------------------

def test_language_hint_overrides_detection():
    """Explicit language_hint wins over script auto-detection."""
    llm_resp = {
        "intent": "tabular_query",
        "entities": {},
        "confidence": 0.8,
        "reasoning": "ok",
    }
    # Pure-English query but caller forces Kannada hint
    with _mock_llm(llm_resp):
        out = index.route(_build_request("show thefts", language_hint="kn"))
    assert out.language == "kn"


def test_language_auto_detects_english_from_ascii():
    assert index.detect_language("show thefts", "auto") == "en"


def test_language_auto_detects_kannada_from_script():
    assert index.detect_language("ಕಳ್ಳತನ", "auto") == "kn"


def test_semantic_query_is_coerced_to_lookup():
    """The prompt taxonomy emits semantic_query; the public contract restricts
    output to the 7 allowed labels — so semantic_query must map to lookup."""
    llm_resp = {
        "intent": "semantic_query",
        "entities": {"similarity_anchor": "Indiranagar metro"},
        "confidence": 0.85,
        "reasoning": "RAG over narratives.",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("cases similar to Indiranagar metro"))
    assert out.intent == "lookup"


def test_llm_wrapped_in_code_fence_is_parsed():
    """Qwen occasionally wraps JSON in ```json fences despite instructions."""
    fenced = "```json\n" + json.dumps({
        "intent": "tabular_query",
        "entities": {"crime_type": "theft"},
        "confidence": 0.9,
        "reasoning": "ok",
    }) + "\n```"
    with patch.object(index.catalyst_client, "quickml_chat", return_value=fenced):
        out = index.route(_build_request("thefts in MG Road"))
    assert out.intent == "tabular_query"


def test_invalid_llm_intent_falls_back_to_heuristic():
    """If the LLM returns an unknown intent label, fall back to heuristic
    classification rather than crash."""
    bad = json.dumps({
        "intent": "definitely_not_a_real_intent",
        "entities": {},
        "confidence": 0.9,
        "reasoning": "broken",
    })
    with patch.object(index.catalyst_client, "quickml_chat", return_value=bad):
        # Also disable Gemini fallback so we exercise the heuristic path
        with patch.object(index, "_GEMINI_FALLBACK", False):
            out = index.route(_build_request("Will thefts increase next week"))
    # Heuristic should pick predictive based on "will" + "next week"
    assert out.intent == "predictive_query"
    assert out.confidence <= 0.5  # heuristic confidence is capped low


def test_quickml_failure_then_gemini_failure_uses_heuristic():
    """When BOTH LLMs fail, the deterministic heuristic must keep the
    function alive — investigators can't see a crash."""
    def _boom(*args, **kwargs):
        raise index.catalyst_client.CatalystClientError("simulated outage")

    with patch.object(index.catalyst_client, "quickml_chat", side_effect=_boom):
        with patch.object(index, "_GEMINI_FALLBACK", False):
            out = index.route(_build_request("Who is connected to Ravi Kumar"))
    # Heuristic sees "connected to" => graph_query
    assert out.intent == "graph_query"
    assert out.confidence <= 0.5


def test_empty_query_is_rejected_at_validation():
    """Pydantic input model must reject empty queries."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        index.RouterRequest(query="", language_hint="en")


def test_response_shape_matches_contract():
    """Lock the response keys so future refactors can't silently break the
    Circuit contract."""
    llm_resp = {
        "intent": "tabular_query",
        "entities": {"crime_type": "theft"},
        "confidence": 0.9,
        "reasoning": "ok",
    }
    with _mock_llm(llm_resp):
        out = index.route(_build_request("show thefts"))
    payload = out.model_dump()
    assert set(payload.keys()) == {
        "intent",
        "language",
        "entities",
        "confidence",
        "reasoning",
        "router_latency_ms",
        "request_id",
    }


# ---------------------------------------------------------------------------
# Flask endpoint smoke test
# ---------------------------------------------------------------------------

def test_post_endpoint_returns_200():
    """End-to-end: POST / with valid JSON returns a router decision."""
    llm_resp = {
        "intent": "tabular_query",
        "entities": {"crime_type": "theft"},
        "confidence": 0.9,
        "reasoning": "ok",
    }
    with _mock_llm(llm_resp):
        client = index.app.test_client()
        resp = client.post("/", json={
            "query": "show thefts last month",
            "language_hint": "auto",
            "session_id": "s1",
            "user_role": "sub_inspector",
        })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["intent"] == "tabular_query"
    assert body["language"] == "en"
    assert "request_id" in body


def test_post_endpoint_rejects_invalid_payload():
    client = index.app.test_client()
    resp = client.post("/", json={"language_hint": "en"})  # missing query
    assert resp.status_code == 422


def test_health_endpoint():
    client = index.app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["prompt_version"] == index.prompts.PROMPT_VERSION
