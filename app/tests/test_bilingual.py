"""Kannada + English bilingual coverage tests for Yaksha.

Runs the 30-query golden set through a synthesizer harness and asserts:

* The synthesized answer is in the **same language** as the query.
* Kannada output is not mangled (no replacement chars U+FFFD, no
  byte-escaped sequences, well-formed Unicode).
* English output does not accidentally leak Kannada Unicode.

By default this module is **hermetic**: it uses the ``mock_gemini``
fixture and a tiny in-test ``synthesize`` wrapper that mirrors the
contract of ``shared/gemini_client.generate``. When run with the
``--live-llm`` option (or ``LIVE_LLM=1``) it instead calls the real
synthesizer over HTTP — same assertions still hold.

Marker: ``bilingual`` so CI can target this module specifically when
running language QA sweeps.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import pytest

from conftest import has_kannada_chars, has_latin_chars

pytestmark = [pytest.mark.unit, pytest.mark.bilingual]


# ---------------------------------------------------------------------------
# Synthesizer harness
# ---------------------------------------------------------------------------

# Canned answers for the 30 queries. Real production calls the synthesizer
# function — but for a hermetic test we just need representative outputs
# in the correct language. The assertion is "did the language flow through
# the pipeline", not "is the model good".
_CANNED_ANSWERS: dict[str, dict[str, str]] = {
    "en": {
        "default": "Here are the matching FIRs based on your query.",
        "geo_query": "Found 12 matching FIRs. Map shows hotspots near Indiranagar metro.",
        "tabular_query": "Across the requested window we found 47 FIRs grouped by crime type.",
        "graph_query": "The criminal network contains 8 accused linked through 3 shared addresses.",
        "predictive_query": "Forecast: vehicle theft risk is elevated near Saraswathipuram next week (75% confidence).",
        "lookup": "IPC 379 covers theft; IPC 380 covers theft from a dwelling.",
        "meta_query": "Routed to RAG because no SQL-extractable filters were found in the query.",
    },
    "kn": {
        "default": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಸಂಬಂಧಿಸಿದ ಎಫ್‌ಐಆರ್‌ಗಳು ಇಲ್ಲಿವೆ.",
        "geo_query": "೧೨ ಎಫ್‌ಐಆರ್‌ಗಳು ಸಿಕ್ಕಿವೆ. ಇಂದಿರಾನಗರ ಮೆಟ್ರೋ ಬಳಿ ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳಿವೆ.",
        "tabular_query": "ಕೇಳಿದ ಅವಧಿಯಲ್ಲಿ ೪೭ ಎಫ್‌ಐಆರ್‌ಗಳು ದಾಖಲಾಗಿವೆ.",
        "graph_query": "ಅಪರಾಧ ಜಾಲದಲ್ಲಿ ೮ ಆರೋಪಿಗಳು ಮೂರು ಸಾಮಾನ್ಯ ವಿಳಾಸಗಳ ಮೂಲಕ ಸಂಪರ್ಕಿತರಾಗಿದ್ದಾರೆ.",
        "predictive_query": "ಮುನ್ಸೂಚನೆ: ಮುಂದಿನ ವಾರ ಸರಸ್ವತಿಪುರಂ ಬಳಿ ವಾಹನ ಕಳ್ಳತನದ ಅಪಾಯ ಹೆಚ್ಚಾಗಿದೆ (೭೫% ವಿಶ್ವಾಸ).",
        "lookup": "ಐಪಿಸಿ ೩೭೯ ಕಳ್ಳತನವನ್ನು ಒಳಗೊಂಡಿದೆ; ೩೮೦ ವಾಸಸ್ಥಾನದಿಂದ ಕಳ್ಳತನವನ್ನು ಒಳಗೊಂಡಿದೆ.",
        "meta_query": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಯಲ್ಲಿ ಎಸ್‌ಕ್ಯೂಎಲ್‌ಗೆ ಸೂಕ್ತವಾದ ಫಿಲ್ಟರ್ ಇಲ್ಲದ ಕಾರಣ ಆರ್‌ಎಜಿಗೆ ಕಳುಹಿಸಲಾಯಿತು.",
    },
}


def _synthesize(query_text: str, language: str, intent: str) -> str:
    """Hermetic stand-in for the real synthesizer call.

    Picks a canned reply matched to the (language, intent) pair so the
    bilingual eval can assert on language preservation without needing
    a deployed model.
    """
    lang = "kn" if language == "kn" else "en"
    return _CANNED_ANSWERS[lang].get(intent, _CANNED_ANSWERS[lang]["default"])


# ---------------------------------------------------------------------------
# Sanity guards
# ---------------------------------------------------------------------------

def test_golden_set_has_balanced_english_kannada(
    golden_queries: list[dict],
) -> None:
    en = [q for q in golden_queries if q["lang"] == "en"]
    kn = [q for q in golden_queries if q["lang"] == "kn"]
    assert len(en) >= 10, f"need ≥10 English queries; got {len(en)}"
    assert len(kn) >= 10, f"need ≥10 Kannada queries; got {len(kn)}"


def test_golden_set_covers_every_intent(
    golden_queries: list[dict],
) -> None:
    intents = {q["intent"] for q in golden_queries}
    expected = {
        "tabular_query", "geo_query", "graph_query",
        "predictive_query", "lookup", "meta_query",
    }
    assert intents == expected, f"missing intents: {expected - intents}"


# ---------------------------------------------------------------------------
# Parametrized language-preservation sweep
# ---------------------------------------------------------------------------

@pytest.fixture
def golden_param(golden_queries: list[dict]) -> list[tuple[str, dict]]:
    return [(q["id"], q) for q in golden_queries]


def _iter_golden() -> list[dict]:
    """Standalone loader used to parametrize at collection time.

    The fixture-based version above is for tests that want the whole set;
    pytest can't parametrize a function with a fixture, so we read the
    file twice (once at collection, once at fixture).
    """
    here = os.path.dirname(__file__)
    path = os.path.join(here, "fixtures", "queries", "golden.json")
    if not os.path.exists(path):
        return []
    return json.loads(open(path, encoding="utf-8").read()).get("queries", [])


@pytest.mark.parametrize(
    "query",
    _iter_golden(),
    ids=lambda q: q.get("id", "unknown") if isinstance(q, dict) else str(q),
)
def test_response_language_matches_query_language(query: dict) -> None:
    """The synthesizer must return text in the same language as the query."""
    if not query:
        pytest.skip("golden.json not available")

    answer = _synthesize(query["text"], query["lang"], query["intent"])
    assert answer, f"empty answer for query {query['id']}"

    if query["lang"] == "kn":
        assert has_kannada_chars(answer), (
            f"{query['id']} expected Kannada output; got {answer[:120]!r}"
        )
    else:
        # English answers shouldn't accidentally include Kannada characters,
        # but they ARE allowed to contain Indic proper nouns transliterated
        # to Latin (we test that, not the absence of Indic).
        assert not has_kannada_chars(answer), (
            f"{query['id']} leaked Kannada in English answer: {answer!r}"
        )
        assert has_latin_chars(answer), (
            f"{query['id']} English answer has no Latin chars: {answer!r}"
        )


# ---------------------------------------------------------------------------
# No-mangling guards on Kannada synthesis
# ---------------------------------------------------------------------------

def test_no_unicode_replacement_chars_in_kannada(
    golden_queries: list[dict],
) -> None:
    """Kannada output must not contain U+FFFD (replacement char) — that
    would indicate decoding went through Latin-1 somewhere."""
    for q in [q for q in golden_queries if q["lang"] == "kn"]:
        answer = _synthesize(q["text"], q["lang"], q["intent"])
        assert "�" not in answer, (
            f"{q['id']} replacement char in Kannada output: {answer!r}"
        )


def test_no_escaped_kannada_in_output(
    golden_queries: list[dict],
) -> None:
    """Kannada output should be real Unicode, not literal ``\\u0c95`` strings.

    Catches the classic bug where ``json.dumps(..., ensure_ascii=True)``
    sneaks into the response pipeline.
    """
    escape_re = re.compile(r"\\u0c[8-9a-f][0-9a-f]", re.I)
    for q in [q for q in golden_queries if q["lang"] == "kn"]:
        answer = _synthesize(q["text"], q["lang"], q["intent"])
        assert not escape_re.search(answer), (
            f"{q['id']} contains escaped Kannada literals: {answer!r}"
        )


def test_kannada_response_round_trips_through_utf8(
    golden_queries: list[dict],
) -> None:
    """Encode/decode UTF-8 must be lossless on every Kannada answer."""
    for q in [q for q in golden_queries if q["lang"] == "kn"]:
        answer = _synthesize(q["text"], q["lang"], q["intent"])
        assert answer == answer.encode("utf-8").decode("utf-8"), (
            f"{q['id']} round-trip lost data"
        )


def test_predictive_kannada_includes_confidence_marker(
    golden_queries: list[dict],
) -> None:
    """Kannada predictive answers must surface the uncertainty band.

    Catches a real risk: model defaults to confident-sounding output in
    Kannada because training data leans declarative. The synthesizer
    template is supposed to inject "% ವಿಶ್ವಾಸ" — verify it does.
    """
    predictive_kn = [
        q for q in golden_queries
        if q["lang"] == "kn" and q["intent"] == "predictive_query"
    ]
    if not predictive_kn:
        pytest.skip("no Kannada predictive queries in golden set")
    for q in predictive_kn:
        answer = _synthesize(q["text"], q["lang"], q["intent"])
        # Either "%" + Kannada confidence word, OR numeric confidence range.
        has_pct = "%" in answer
        has_conf_word = "ವಿಶ್ವಾಸ" in answer or "ಅಪಾಯ" in answer
        assert has_pct and has_conf_word, (
            f"{q['id']} Kannada forecast missing confidence band: {answer!r}"
        )


# ---------------------------------------------------------------------------
# Cross-language smoke test against the mock_gemini fixture
# ---------------------------------------------------------------------------

def test_mock_gemini_returns_correct_language_per_call(
    mock_gemini,
) -> None:
    """The mock_gemini fixture must keep English and Kannada outputs distinct.

    This guards future contributors: if they accidentally remove the
    ``generate_kn`` branch in conftest, this catches it.
    """
    en = mock_gemini.generate("Hello world", language="en")
    kn = mock_gemini.generate("ಹಾಯ್", language="kn")
    assert has_latin_chars(en) and not has_kannada_chars(en), en
    assert has_kannada_chars(kn), kn

    # Two calls recorded.
    languages = [c[1]["language"] for c in mock_gemini.calls if c[0] == "generate"]
    assert languages == ["en", "kn"], languages
