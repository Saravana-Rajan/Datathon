"""Tests for the RAG retriever Catalyst Function.

Run with:
    cd app/backend/functions/rag-retriever
    pytest -q

The tests stub out the Gemini SDK and Catalyst SDK so they run with zero
external dependencies — the function logic (filters, ranking, language
mixing) is what we care about here.
"""

from __future__ import annotations

import json
import math
import os
import sys
import types
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Make `index` and `embedder` importable as top-level modules + ensure the
# repo's `shared/` is on sys.path so the shared gemini client can be stubbed.
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


EMBED_DIM = 8  # tiny dim for fast deterministic tests


# ---------------------------------------------------------------------------
# Fixtures — deterministic fake embedder + fake NoSQL corpus
# ---------------------------------------------------------------------------

def _toy_vec(text: str) -> list[float]:
    """Deterministic toy embedding: hash-derived unit-ish vector.

    Same text always yields the same vector. Two strings that share tokens
    score higher than unrelated strings — enough signal to test ranking.
    """
    text_l = (text or "").lower()
    tokens = [t for t in text_l.replace(".", " ").replace(",", " ").split() if t]
    vec = [0.0] * EMBED_DIM
    for tok in tokens:
        idx = (sum(ord(c) for c in tok)) % EMBED_DIM
        vec[idx] += 1.0
    # Normalise so cosine sim is meaningful
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture
def fake_shared_gemini(monkeypatch):
    """Patch shared.gemini_client to use our toy embedder."""
    fake = types.ModuleType("shared.gemini_client")

    class _FakeEmbeddingClient:
        def __init__(self, model: str = "fake-model"):
            self.model = model

        def embed(self, texts, *, task_type="RETRIEVAL_DOCUMENT"):
            return [_toy_vec(t) for t in texts]

    def get_embedding_client(model=None):
        return _FakeEmbeddingClient(model or "fake-model")

    fake.get_embedding_client = get_embedding_client  # type: ignore[attr-defined]
    # Also stash a placeholder for the text client so any incidental imports work
    fake.get_text_client = lambda model=None: None  # type: ignore[attr-defined]

    # Ensure the `shared` package exists in sys.modules for `from shared import ...`
    shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
    shared_pkg.gemini_client = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "shared.gemini_client", fake)

    # Also blow away the embedder's cached reference so it re-resolves
    import embedder  # type: ignore
    embedder._SHARED_GEMINI = None  # type: ignore[attr-defined]
    yield fake
    embedder._SHARED_GEMINI = None  # type: ignore[attr-defined]


def _make_corpus() -> list[dict[str, Any]]:
    """Build a small mixed Kannada/English corpus and pre-embed it."""
    raw = [
        {
            "fir_no": "BLR/IND/2025/0142",
            "text": "Vehicle theft of two-wheeler near Indiranagar metro station at night.",
            "text_kn": "ರಾತ್ರಿಯ ವೇಳೆ ಇಂದಿರಾನಗರ ಮೆಟ್ರೋ ನಿಲ್ದಾಣದ ಬಳಿ ದ್ವಿಚಕ್ರ ವಾಹನ ಕಳ್ಳತನ.",
            "crime_type": "vehicle_theft",
            "district": "Bengaluru Urban",
            "date": "2025-11-12",
        },
        {
            "fir_no": "BLR/JN/2026/0010",
            "text": "Chain snatching by two suspects on motorcycle near Jayanagar 4th block.",
            "text_kn": "ಜಯನಗರ 4ನೇ ಬ್ಲಾಕ್ ಬಳಿ ಚೈನ್ ಕಳ್ಳತನ.",
            "crime_type": "chain_snatching",
            "district": "Bengaluru Urban",
            "date": "2026-02-04",
        },
        {
            "fir_no": "MYS/CT/2025/0091",
            "text": "Burglary at residence in Mysuru, valuables and cash missing.",
            "text_kn": "ಮೈಸೂರಿನ ನಿವಾಸದಲ್ಲಿ ಕಳ್ಳತನ.",
            "crime_type": "burglary",
            "district": "Mysuru",
            "date": "2025-08-20",
        },
        {
            "fir_no": "BLR/WF/2025/2008",
            "text": "Stolen vehicle recovered abandoned near Whitefield, suspected vehicle theft ring.",
            "text_kn": "ವೈಟ್‌ಫೀಲ್ಡ್‌ ಬಳಿ ವಾಹನ ಕಳ್ಳತನ ಪ್ರಕರಣ.",
            "crime_type": "vehicle_theft",
            "district": "Bengaluru Urban",
            "date": "2026-01-30",
        },
        {
            "fir_no": "HUB/01/2024/4421",
            "text": "Cyber fraud — UPI phishing scam reported by complainant.",
            "text_kn": "ಸೈಬರ್ ವಂಚನೆ ಪ್ರಕರಣ.",
            "crime_type": "cyber_fraud",
            "district": "Hubballi-Dharwad",
            "date": "2024-12-01",
        },
    ]
    for row in raw:
        # Embed the English text — the toy embedder is language-agnostic anyway,
        # we just want stable vectors that mirror lexical overlap.
        row["embedding"] = _toy_vec(row["text"] + " " + row["text_kn"])
    return raw


@pytest.fixture
def fake_catalyst_corpus(monkeypatch):
    """Patch shared.catalyst_client.get_nosql to return our toy corpus."""
    corpus = _make_corpus()

    class _FakeTable:
        def fetch_all_items(self):
            return [{"item": row} for row in corpus]

    class _FakeNoSQL:
        def table(self, name):
            return _FakeTable()

    fake_cc = types.ModuleType("shared.catalyst_client")

    def get_nosql(context=None):
        return _FakeNoSQL()

    fake_cc.get_nosql = get_nosql  # type: ignore[attr-defined]
    fake_cc.get_datastore = lambda context=None: None  # type: ignore[attr-defined]
    fake_cc.log_audit = lambda *a, **kw: "fake-req-id"  # type: ignore[attr-defined]

    shared_pkg = sys.modules.get("shared") or types.ModuleType("shared")
    shared_pkg.catalyst_client = fake_cc  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "shared.catalyst_client", fake_cc)

    yield corpus


@pytest.fixture(autouse=True)
def force_gemini_path(monkeypatch):
    """All tests exercise the Gemini fallback path — pin the env flag and
    make sure no QuickML endpoint is configured.
    """
    monkeypatch.setenv("USE_GEMINI_EMBEDDINGS", "true")
    monkeypatch.delenv("QUICKML_RAG_ENDPOINT", raising=False)
    monkeypatch.delenv("QUICKML_RAG_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_embed_query_returns_vector(fake_shared_gemini):
    """embed_query returns a non-empty vector matching the embedder dim."""
    from embedder import embed_query  # type: ignore
    vec = embed_query("vehicle theft")
    assert isinstance(vec, list)
    assert len(vec) == EMBED_DIM
    assert all(isinstance(v, float) for v in vec)
    # Norm should be approximately 1 (toy embedder normalises)
    norm = math.sqrt(sum(v * v for v in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-6)


def test_embed_query_empty_string(fake_shared_gemini):
    """Empty input returns an empty vector — caller should skip retrieval."""
    from embedder import embed_query  # type: ignore
    assert embed_query("") == []
    assert embed_query("   ") == []


def test_embed_batch_preserves_order_and_empties(fake_shared_gemini):
    """embed_batch keeps order; empty strings come back as empty vectors."""
    from embedder import embed_batch  # type: ignore
    texts = ["vehicle theft", "", "chain snatching"]
    vecs = embed_batch(texts)
    assert len(vecs) == 3
    assert len(vecs[0]) == EMBED_DIM
    assert vecs[1] == []
    assert len(vecs[2]) == EMBED_DIM


def test_cosine_search_descending_scores(fake_shared_gemini, fake_catalyst_corpus):
    """The retriever returns passages sorted by descending similarity."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    passages, method = idx.retrieve("vehicle theft near Indiranagar", top_k=4)
    assert method == "gemini_embed"
    assert len(passages) >= 2
    scores = [p["score"] for p in passages]
    assert scores == sorted(scores, reverse=True)
    # The vehicle-theft FIRs should rank above the cyber-fraud one
    top_fir_nos = {p["fir_no"] for p in passages[:2]}
    assert any("BLR/IND" in fno or "BLR/WF" in fno for fno in top_fir_nos)
    # All scores normalised into [0, 1]
    for s in scores:
        assert 0.0 <= s <= 1.0


def test_filter_by_crime_type_narrows_results(fake_shared_gemini, fake_catalyst_corpus):
    """Adding crime_type=burglary drops all non-burglary FIRs."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    passages, _ = idx.retrieve(
        "missing valuables", top_k=5, filters={"crime_type": "burglary"},
    )
    assert passages, "expected at least one burglary hit"
    for p in passages:
        assert p["metadata"]["crime_type"] == "burglary"


def test_filter_by_district_and_date_range(fake_shared_gemini, fake_catalyst_corpus):
    """District + date_range filters both narrow results."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    passages, _ = idx.retrieve(
        "vehicle theft",
        top_k=5,
        filters={
            "district": "Bengaluru Urban",
            "date_range": {"from": "2025-10-01", "to": "2026-12-31"},
        },
    )
    assert passages
    for p in passages:
        assert p["metadata"]["district"] == "Bengaluru Urban"
        assert p["metadata"]["date"] >= "2025-10-01"


def test_kannada_query_returns_mixed_passages(fake_shared_gemini, fake_catalyst_corpus):
    """A Kannada query still retrieves passages carrying BOTH text and text_kn."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    kn_query = "ವಾಹನ ಕಳ್ಳತನ ಇಂದಿರಾನಗರ"  # "vehicle theft Indiranagar"
    passages, method = idx.retrieve(kn_query, language="kn", top_k=3)
    assert method == "gemini_embed"
    assert passages
    # Every passage should expose both English and Kannada text fields
    for p in passages:
        assert "narrative" in p and "narrative_kannada" in p
        assert isinstance(p["narrative"], str)
        assert isinstance(p["narrative_kannada"], str)
        # At least one passage should have a non-empty Kannada narrative
    assert any(p["narrative_kannada"] for p in passages)
    # And at least one English narrative
    assert any(p["narrative"] for p in passages)


def test_handler_returns_well_formed_response(fake_shared_gemini, fake_catalyst_corpus):
    """The full handler path produces the documented response shape."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    class _FakeReq:
        def get_json(self):
            return {
                "request_id": "test-1",
                "query": "chain snatching jayanagar",
                "language": "en",
                "top_k": 3,
                "filters": {"crime_type": "chain_snatching"},
            }

    class _FakeRes:
        def __init__(self):
            self.status = None
            self.body = None
            self.content_type = None
        def set_status(self, s): self.status = s
        def set_content_type(self, ct): self.content_type = ct
        def send(self, payload): self.body = payload

    fake_res = _FakeRes()

    class _FakeBasicIO:
        pass

    basic_io = _FakeBasicIO()
    basic_io.req = _FakeReq()
    basic_io.res = fake_res

    body = idx.handler(context=None, basic_io=basic_io)
    assert body["ok"] is True
    assert body["request_id"] == "test-1"
    assert body["method_used"] in {"quickml", "gemini_embed"}
    assert "passages" in body and isinstance(body["passages"], list)
    assert fake_res.status == 200
    decoded = json.loads(fake_res.body)
    assert decoded["passages"] == body["passages"]


def test_handler_missing_query_returns_400(fake_shared_gemini, fake_catalyst_corpus):
    """Empty query body fails fast with HTTP 400."""
    import importlib
    import index as idx  # type: ignore
    importlib.reload(idx)

    class _FakeReq:
        def get_json(self):
            return {"request_id": "test-2", "query": "   "}

    class _FakeRes:
        def __init__(self):
            self.status = None
            self.body = None
        def set_status(self, s): self.status = s
        def set_content_type(self, ct): pass
        def send(self, p): self.body = p

    fake_res = _FakeRes()

    class _FakeBasicIO:
        pass

    basic_io = _FakeBasicIO()
    basic_io.req = _FakeReq()
    basic_io.res = fake_res

    body = idx.handler(context=None, basic_io=basic_io)
    assert body["ok"] is False
    assert fake_res.status == 400


def test_cosine_similarity_helper_math():
    """Cosine helper handles edge cases — empty, zero, mismatched length."""
    from embedder import cosine_similarity  # type: ignore
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0  # length mismatch
