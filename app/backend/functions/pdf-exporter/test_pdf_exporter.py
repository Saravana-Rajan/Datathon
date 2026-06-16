"""Tests for the KSP Saathi PDF exporter Catalyst Function.

Coverage targets (all five required by the task):

    1. Renders sample template with a mock session.
    2. Asserts the rendered HTML contains both English AND Kannada text
       correctly (Unicode preserved, autoescape-aware).
    3. Mocks SmartBrowz, asserts it's called the expected number of times
       for both screenshots and HTML→PDF.
    4. Verifies Stratus upload happens and a signed URL is returned in the
       handler response.
    5. Plus a couple of guard tests around the request validation surface
       so 400 / 404 paths don't silently regress.

Run from this directory with::

    pytest -v test_pdf_exporter.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

# Make the function module importable without packaging gymnastics.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import index as exporter  # noqa: E402  — module under test


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KANNADA_QUESTION = "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕಳೆದ ತಿಂಗಳು ಸಂಭವಿಸಿದ ಸರಗಳ್ಳತನ ಪ್ರಕರಣಗಳನ್ನು ತೋರಿಸಿ"
KANNADA_ANSWER = "ಕಳೆದ 30 ದಿನಗಳಲ್ಲಿ ಇಂದಿರಾ ನಗರ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ 14 ಸರಗಳ್ಳತನ ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ."
ENGLISH_QUESTION = "Show chain snatchings near Indiranagar metro in the last 30 days"
ENGLISH_ANSWER = (
    "14 chain-snatching FIRs were registered within 1.5 km of Indiranagar metro "
    "between 17 May and 16 Jun 2026. [FIR-2026-BLR-IND-0142]"
)


@pytest.fixture
def sample_session() -> dict[str, Any]:
    return {
        "session_id": "sess_test_001",
        "officer_name": "PSI Manjunath B.",
        "officer_role": "Sub-Inspector",
        "jurisdiction": "Indiranagar PS, Bengaluru East",
        "start_time": "2026-06-16T09:12:04Z",
        "end_time": "2026-06-16T09:21:47Z",
        "language_pref": "kn",
        "turns": [
            {
                "request_id": "req-aaa-001",
                "timestamp": "2026-06-16T09:12:30Z",
                "language": "kn",
                "raw_query": KANNADA_QUESTION,
                "query_en": ENGLISH_QUESTION,
                "query_kn": KANNADA_QUESTION,
                "response": KANNADA_ANSWER,
                "response_en": ENGLISH_ANSWER,
                "response_kn": KANNADA_ANSWER,
                "intent": "tabular_geo",
                "latency_ms": 2810,
                "sources": [
                    {"id": "FIR-2026-BLR-IND-0142"},
                    {"id": "FIR-2026-BLR-IND-0151"},
                ],
                "viz_spec": {
                    "map": {
                        "center": {"lat": 12.9784, "lng": 77.6408},
                        "zoom": 14,
                        "markers": [
                            {"lat": 12.9784, "lng": 77.6408, "label": "A"},
                            {"lat": 12.9772, "lng": 77.6391, "label": "B"},
                        ],
                    },
                    "graph": {"node_count": 7, "edge_count": 9},
                },
            },
            {
                "request_id": "req-aaa-002",
                "timestamp": "2026-06-16T09:18:11Z",
                "language": "en",
                "raw_query": "Who is the most-linked accused?",
                "query_en": "Who is the most-linked accused?",
                "response": "Accused #A-04412 appears in 6 of the 14 FIRs. [graph:node_42]",
                "response_en": "Accused #A-04412 appears in 6 of the 14 FIRs. [graph:node_42]",
                "intent": "graph_query",
                "latency_ms": 1920,
                "sources": [{"id": "graph:node_42"}],
                "viz_spec": {"graph": {"node_count": 12}},
            },
        ],
    }


@pytest.fixture
def sample_audit() -> list[dict[str, Any]]:
    return [
        {
            "request_id": "req-aaa-001",
            "ts": 1750068750000,
            "ts_iso": "2026-06-16T09:12:30Z",
            "user_id": "psi-manjunath",
            "role": "sub_inspector",
            "language": "kn",
            "raw_query": KANNADA_QUESTION,
            "intent": "tabular_geo",
            "route_decision": "tabular+geo",
            "sql": "SELECT * FROM firs WHERE district='Bengaluru Urban' AND crime_type='chain_snatching'",
            "sources": [{"id": "FIR-2026-BLR-IND-0142"}],
            "response": KANNADA_ANSWER,
            "latency_ms": 2810,
            "confidence": 0.86,
        },
        {
            "request_id": "req-aaa-002",
            "ts": 1750069091000,
            "ts_iso": "2026-06-16T09:18:11Z",
            "user_id": "psi-manjunath",
            "role": "sub_inspector",
            "language": "en",
            "raw_query": "Who is the most-linked accused?",
            "intent": "graph_query",
            "route_decision": "graph",
            "cypher": "MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR) WHERE f.fir_no IN $list RETURN p ORDER BY count(*) DESC",
            "sources": [{"id": "graph:node_42"}],
            "response": "Accused #A-04412 appears in 6 of the 14 FIRs.",
            "latency_ms": 1920,
            "confidence": 0.91,
        },
    ]


# ---------------------------------------------------------------------------
# 1 + 2. Template rendering — English + Kannada content preserved
# ---------------------------------------------------------------------------

def test_render_html_contains_english_text(sample_session, sample_audit):
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="both",
        include_audit=True,
        audit_entries=sample_audit,
        export_request_id="exp-test-001",
        generated_at="2026-06-16T09:25:00.000000Z",
    )

    # Letterhead + KSP branding
    assert "KARNATAKA STATE POLICE" in html
    assert "Generated by KSP Saathi v1.0" in html

    # English question + answer present
    assert ENGLISH_QUESTION in html
    assert "14 chain-snatching FIRs" in html
    assert "[FIR-2026-BLR-IND-0142]" in html

    # Officer metadata + session id
    assert "PSI Manjunath B." in html
    assert "Sub-Inspector" in html
    assert "sess_test_001" in html


def test_render_html_contains_kannada_text(sample_session):
    """Kannada glyphs must survive Jinja2 autoescape + ensure_ascii=False handling."""
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="both",
        include_audit=False,
        export_request_id="exp-test-002",
        generated_at="2026-06-16T09:25:00.000000Z",
    )

    # Kannada question and answer in the literal output
    assert KANNADA_QUESTION in html
    assert KANNADA_ANSWER in html

    # Kannada letterhead label
    assert "ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೋಲೀಸ್" in html

    # Font-face for Noto Sans Kannada was emitted (so the PDF can render glyphs)
    assert "Noto Sans Kannada" in html
    assert 'lang="kn"' in html  # the Kannada blocks are tagged


def test_render_html_language_filter_kn_only(sample_session):
    """When language='kn' the English-only blocks must not appear."""
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="kn",
        include_audit=False,
    )
    # Kannada Q present
    assert KANNADA_QUESTION in html
    # English Q block NOT present (the EN-only label "Officer Question (EN)")
    assert "Officer Question (EN)" not in html
    # Language label reflects choice
    assert "ಕನ್ನಡ" in html


def test_render_html_language_filter_en_only(sample_session):
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="en",
        include_audit=False,
    )
    assert ENGLISH_QUESTION in html
    # The KN-only label should not appear
    assert "ಅಧಿಕಾರಿಯ ಪ್ರಶ್ನೆ (KN)" not in html


def test_render_html_audit_appendix_appears(sample_session, sample_audit):
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="both",
        include_audit=True,
        audit_entries=sample_audit,
    )
    assert "Audit Trail Appendix" in html
    assert "req-aaa-001" in html
    assert "req-aaa-002" in html
    # SQL and Cypher both rendered (truncated by `| truncate`)
    assert "SELECT * FROM firs" in html
    assert "MATCH (p:Person)" in html


def test_render_html_audit_omitted_when_disabled(sample_session, sample_audit):
    html = exporter.render_html(
        session=sample_session,
        turns=sample_session["turns"],
        language="both",
        include_audit=False,
        audit_entries=sample_audit,
    )
    assert "Audit Trail Appendix" not in html


# ---------------------------------------------------------------------------
# 3. SmartBrowz mock — screenshots + PDF render must both be called
# ---------------------------------------------------------------------------

def test_smartbrowz_called_for_screenshots_and_pdf(monkeypatch, sample_session, sample_audit):
    """End-to-end: export_session_pdf calls SmartBrowz once per snapshot + once for PDF."""

    # Provide a Google Maps key so the static-Maps URL builder activates
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "TEST_KEY", raising=False)
    monkeypatch.setattr(exporter, "GRAPH_RENDER_BASE", "https://app.kspsaathi.in", raising=False)
    monkeypatch.setattr(exporter, "SMARTBROWZ_API_KEY", "stub-key", raising=False)

    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path: str, payload: dict[str, Any], *, timeout: float | None = None) -> bytes:
        calls.append((path, payload))
        if path == "screenshot":
            # A 1x1 transparent PNG — valid bytes for the data-URI test
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00"
                b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
        if path == "pdf":
            return b"%PDF-1.4\n%mocked-pdf-bytes\n%%EOF\n"
        raise AssertionError(f"unexpected SmartBrowz path: {path}")

    monkeypatch.setattr(exporter, "_smartbrowz_post", fake_post)

    # Stub Stratus upload so we don't hit Catalyst NoSQL/Stratus
    monkeypatch.setattr(
        exporter, "upload_to_stratus",
        lambda pdf_bytes, key, context=None: f"https://stratus.test/{key}?sig=stub",
    )

    result = exporter.export_session_pdf(
        sample_session["session_id"],
        include_audit=True,
        language="both",
        session_override=sample_session,
        audit_override=sample_audit,
    )

    # PDF endpoint MUST have been called exactly once
    pdf_calls = [c for c in calls if c[0] == "pdf"]
    assert len(pdf_calls) == 1, f"expected 1 PDF call, got {len(pdf_calls)}: {calls}"
    # The HTML that hit SmartBrowz must contain both the EN and KN strings
    rendered_html = pdf_calls[0][1]["html"]
    assert ENGLISH_QUESTION in rendered_html
    assert KANNADA_QUESTION in rendered_html
    # And the PDF call uses A4 (case-file standard)
    assert pdf_calls[0][1]["format"] == "A4"

    # Screenshot calls — one map (turn 1 has a map) + two graphs (both turns have graphs).
    # Turn 2 has no map_spec, so only its graph is screenshotted.
    screenshot_calls = [c for c in calls if c[0] == "screenshot"]
    assert len(screenshot_calls) == 3, (
        f"expected 3 SmartBrowz screenshot calls (1 map + 2 graphs), "
        f"got {len(screenshot_calls)}: paths={[c[0] for c in calls]}"
    )
    # At least one screenshot pointed at Google Static Maps
    assert any(
        "maps.googleapis.com" in c[1].get("url", "") for c in screenshot_calls
    ), "no SmartBrowz screenshot was directed at Google Static Maps"

    # Result shape sanity
    assert result["pdf_url"].startswith("https://stratus.test/")
    assert result["size_bytes"] == len(b"%PDF-1.4\n%mocked-pdf-bytes\n%%EOF\n")
    assert result["turns"] == 2
    assert result["session_id"] == "sess_test_001"


def test_smartbrowz_screenshot_failure_is_silent(monkeypatch, sample_session, sample_audit):
    """If SmartBrowz fails on a screenshot, the PDF still ships (just without that image)."""
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "TEST_KEY", raising=False)
    monkeypatch.setattr(exporter, "GRAPH_RENDER_BASE", "https://app.kspsaathi.in", raising=False)
    monkeypatch.setattr(exporter, "SMARTBROWZ_API_KEY", "stub-key", raising=False)

    def flaky_post(path: str, payload: dict[str, Any], *, timeout: float | None = None) -> bytes:
        if path == "screenshot":
            raise RuntimeError("SmartBrowz transient 503")
        return b"%PDF-1.4\n%mock\n%%EOF\n"

    monkeypatch.setattr(exporter, "_smartbrowz_post", flaky_post)
    monkeypatch.setattr(
        exporter, "upload_to_stratus",
        lambda pdf_bytes, key, context=None: f"https://stratus.test/{key}",
    )

    # Should not raise — screenshots are best-effort
    result = exporter.export_session_pdf(
        sample_session["session_id"],
        include_audit=False,
        language="both",
        session_override=sample_session,
        audit_override=sample_audit,
    )
    assert result["pdf_url"].endswith(".pdf")
    assert result["size_bytes"] > 0


# ---------------------------------------------------------------------------
# 4. Stratus upload + URL returned through the handler
# ---------------------------------------------------------------------------

class _FakeBasicIO:
    """Mimics the basic_io wrapper Catalyst injects into handlers."""

    def __init__(self, body: dict[str, Any]):
        self.req = _FakeRequest(body)
        self.res = _FakeResponse()


class _FakeRequest:
    def __init__(self, body: dict[str, Any]):
        self._body = body

    def get_json(self) -> dict[str, Any]:
        return self._body


class _FakeResponse:
    def __init__(self):
        self.status: int | None = None
        self.body: str | None = None
        self.content_type: str | None = None

    def set_status(self, s: int): self.status = s
    def set_content_type(self, ct: str): self.content_type = ct
    def send(self, payload: str): self.body = payload


def test_handler_returns_signed_url_and_uploads_to_stratus(
    monkeypatch, sample_session, sample_audit,
):
    """The full POST handler path — patch all I/O, assert Stratus upload + URL."""
    monkeypatch.setattr(exporter, "SMARTBROWZ_API_KEY", "stub-key", raising=False)
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "TEST_KEY", raising=False)
    monkeypatch.setattr(exporter, "GRAPH_RENDER_BASE", "https://app.kspsaathi.in", raising=False)

    # No real SmartBrowz traffic
    monkeypatch.setattr(
        exporter, "_smartbrowz_post",
        lambda path, payload, **_: (b"\x89PNG\x00stub" if path == "screenshot" else b"%PDF-1.4\nstub\n%%EOF"),
    )
    # No real Catalyst NoSQL — return our fixture session directly
    monkeypatch.setattr(exporter, "_fetch_session", lambda sid, context=None: sample_session)
    monkeypatch.setattr(
        exporter, "_fetch_audit_chain",
        lambda sid, rids, context=None: sample_audit,
    )

    # Capture Stratus upload
    upload_capture: dict[str, Any] = {}

    def fake_upload(pdf_bytes: bytes, object_key: str, *, context: Any = None) -> str:
        upload_capture["pdf_bytes"] = pdf_bytes
        upload_capture["object_key"] = object_key
        upload_capture["context"] = context
        return f"https://ksp-saathi-exports.zohostratus.com/{object_key}?sig=test-sig"

    monkeypatch.setattr(exporter, "upload_to_stratus", fake_upload)

    bio = _FakeBasicIO({
        "session_id": "sess_test_001",
        "include_audit": True,
        "language": "both",
    })

    # context is unused in the patched path; pass an empty MagicMock so attr lookups work
    exporter.handler(MagicMock(), bio)

    # Response captured by FakeResponse.send()
    assert bio.res.status == 200, f"got status {bio.res.status}, body={bio.res.body}"
    payload = json.loads(bio.res.body)

    assert payload["ok"] is True
    assert payload["session_id"] == "sess_test_001"
    assert payload["pdf_url"].startswith("https://ksp-saathi-exports.zohostratus.com/sessions/")
    assert payload["pdf_url"].endswith("?sig=test-sig")
    assert "sessions/sess_test_001.pdf" in payload["pdf_url"]
    assert payload["size_bytes"] > 0
    assert payload["turns"] == 2
    assert payload["generated_at"].endswith("Z")
    assert "export_request_id" in payload
    assert "latency_ms" in payload

    # Stratus upload received our PDF + canonical object key
    assert upload_capture["object_key"] == "sessions/sess_test_001.pdf"
    assert upload_capture["pdf_bytes"].startswith(b"%PDF")


# ---------------------------------------------------------------------------
# 5. Request-validation guard tests
# ---------------------------------------------------------------------------

def test_handler_rejects_missing_session_id():
    bio = _FakeBasicIO({"include_audit": True, "language": "both"})
    exporter.handler(MagicMock(), bio)
    assert bio.res.status == 400
    body = json.loads(bio.res.body)
    assert body["ok"] is False
    assert "session_id" in body["error"]


def test_handler_404_when_session_missing(monkeypatch):
    monkeypatch.setattr(exporter, "_fetch_session", lambda sid, context=None: {})

    bio = _FakeBasicIO({"session_id": "does-not-exist", "language": "en"})
    exporter.handler(MagicMock(), bio)
    assert bio.res.status == 404
    body = json.loads(bio.res.body)
    assert body["ok"] is False
    assert "not found" in body["error"].lower()


def test_handler_normalises_invalid_language(monkeypatch, sample_session, sample_audit):
    """Garbage language values fall back to 'both' rather than 400."""
    monkeypatch.setattr(exporter, "SMARTBROWZ_API_KEY", "stub-key", raising=False)
    monkeypatch.setattr(
        exporter, "_smartbrowz_post",
        lambda path, payload, **_: b"%PDF-1.4\nstub\n%%EOF",
    )
    monkeypatch.setattr(exporter, "_fetch_session", lambda sid, context=None: sample_session)
    monkeypatch.setattr(exporter, "_fetch_audit_chain", lambda sid, rids, context=None: sample_audit)
    monkeypatch.setattr(
        exporter, "upload_to_stratus",
        lambda pdf_bytes, key, context=None: f"https://stratus.test/{key}",
    )

    bio = _FakeBasicIO({"session_id": "sess_test_001", "language": "swahili"})
    exporter.handler(MagicMock(), bio)
    assert bio.res.status == 200
    body = json.loads(bio.res.body)
    assert body["ok"] is True


# ---------------------------------------------------------------------------
# 6. Static-Maps URL builder unit test (cheap sanity check on the snapshot URL)
# ---------------------------------------------------------------------------

def test_static_maps_url_built_correctly(monkeypatch):
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "ABC123", raising=False)
    url = exporter._build_static_maps_url({
        "center": {"lat": 12.97, "lng": 77.59},
        "zoom": 13,
        "markers": [{"lat": 12.97, "lng": 77.59, "label": "A"}],
    })
    assert url is not None
    assert "maps.googleapis.com" in url
    assert "center=12.97,77.59" in url
    assert "zoom=13" in url
    assert "key=ABC123" in url
    assert "markers=color:red" in url


def test_static_maps_url_none_without_center(monkeypatch):
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "ABC123", raising=False)
    assert exporter._build_static_maps_url({}) is None
    assert exporter._build_static_maps_url({"zoom": 14}) is None


def test_static_maps_url_none_without_key(monkeypatch):
    monkeypatch.setattr(exporter, "GOOGLE_MAPS_STATIC_KEY", "", raising=False)
    assert exporter._build_static_maps_url({"center": {"lat": 1, "lng": 2}}) is None
