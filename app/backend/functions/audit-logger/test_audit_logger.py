"""Unit tests for the KSP Saathi audit-logger Catalyst Function.

These tests do NOT require a live Catalyst NoSQL connection. We monkey-
patch `_open_table` to return an in-memory fake that mimics the subset
of the zcatalyst-sdk NoSQL API the function exercises:

    table.insert_items([{"item": {...}}])
    table.fetch_all_items()         # used by _list_table_items

The fake is intentionally minimal but race-aware (a real threading.Lock
guards the items list) so the concurrent-append test exercises the
allocate-then-write flow the deployed function relies on.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make `index` importable without packaging.
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import index  # noqa: E402 — path manipulation above is intentional


# --------------------------------------------------------------------------- #
# In-memory fake NoSQL                                                        #
# --------------------------------------------------------------------------- #


class FakeNoSQLTable:
    """Mimics the subset of zcatalyst-sdk NoSQL table the function uses."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._items: list[dict] = []
        self._lock = threading.Lock()

    def insert_items(self, items):
        with self._lock:
            for wrapper in items:
                item = wrapper.get("item") if isinstance(wrapper, dict) else wrapper
                if isinstance(item, dict):
                    # Catalyst would assign an internal ROWID; we keep `id`.
                    self._items.append(dict(item))

    def fetch_all_items(self):
        with self._lock:
            return [{"item": dict(it)} for it in self._items]

    # Used by _items_for_request server-side filter path.
    def query_items(self, filt: dict):
        request_id = filt.get("request_id")
        with self._lock:
            return [
                {"item": dict(it)}
                for it in self._items
                if it.get("request_id") == request_id
            ]


class FakeTables:
    """Container that hands out (and reuses) FakeNoSQLTable instances."""

    def __init__(self) -> None:
        self._tables: dict[str, FakeNoSQLTable] = {}

    def get(self, name: str) -> FakeNoSQLTable:
        if name not in self._tables:
            self._tables[name] = FakeNoSQLTable(name)
        return self._tables[name]


@pytest.fixture
def fake_tables(monkeypatch) -> FakeTables:
    tables = FakeTables()

    def _fake_open_table(table_name: str, context):
        return tables.get(table_name)

    monkeypatch.setattr(index, "_open_table", _fake_open_table)
    return tables


# --------------------------------------------------------------------------- #
# Request / response fakes                                                    #
# --------------------------------------------------------------------------- #


class FakeRequest:
    def __init__(self, method: str = "POST", path: str = "/append",
                 body: dict | None = None, query: dict | None = None) -> None:
        self.method = method
        self.path = path
        self._body = body or {}
        self.args = query or {}
        self.query_params = self.args

    def get_json(self):
        return self._body


class FakeResponse:
    def __init__(self) -> None:
        self.status: int | None = None
        self.body: str | None = None
        self.content_type: str | None = None

    def set_status(self, status: int) -> None:
        self.status = status

    def set_content_type(self, ct: str) -> None:
        self.content_type = ct

    def send(self, payload: str) -> None:
        self.body = payload


class FakeBasicIO:
    def __init__(self, req: FakeRequest, res: FakeResponse) -> None:
        self.req = req
        self.res = res


def _invoke(req: FakeRequest):
    res = FakeResponse()
    context = MagicMock()
    basic_io = FakeBasicIO(req, res)
    result = index.handler(context, basic_io)
    assert isinstance(result, dict)
    return res.status, result


# --------------------------------------------------------------------------- #
# Append + fetch                                                              #
# --------------------------------------------------------------------------- #


def test_append_five_steps_then_fetch_returns_all_in_order(fake_tables):
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    steps = [
        ("input",           {"text": "show vehicle thefts near Indiranagar"}),
        ("language_detect", {"lang": "en", "confidence": 0.98}),
        ("route",           {"intent": "tabular_geo", "tools": ["sql", "geo"]}),
        ("tool_call",       {"tool": "sql", "latency_ms": 240, "rows": 12}),
        ("synthesis",       {"model": "qwen2.5-14b-instruct", "latency_ms": 410}),
    ]

    for step_type, step_data in steps:
        status, body = _invoke(FakeRequest(
            method="POST",
            path="/append",
            body={
                "request_id": request_id,
                "step_type": step_type,
                "step_data": step_data,
            },
        ))
        assert status == 200, body
        assert body["ok"] is True
        assert body["request_id"] == request_id

    # Fetch
    status, body = _invoke(FakeRequest(
        method="GET",
        path="/",
        query={"request_id": request_id},
    ))
    assert status == 200
    assert body["ok"] is True
    chain = body["chain"]
    assert len(chain) == 5, f"expected 5 steps, got {len(chain)}: {chain}"

    # Ordering: step_index 0..4 in order
    for i, step in enumerate(chain):
        assert step["step_index"] == i, f"step {i} has wrong index: {step}"
        assert step["step_type"] == steps[i][0]

    summary = body["summary"]
    assert summary["step_count"] == 5
    # tool_call (240) + synthesis (410) = 650
    assert summary["total_latency_ms"] == 650
    assert "sql" in summary["tools_used"]
    assert "qwen2.5-14b-instruct" in summary["models_used"]


def test_fetch_unknown_request_id_returns_404(fake_tables):
    status, body = _invoke(FakeRequest(
        method="GET",
        path="/",
        query={"request_id": "does-not-exist-anywhere"},
    ))
    assert status == 404
    assert body["ok"] is False
    assert body["error"] == "not_found"


def test_fetch_without_request_id_returns_400(fake_tables):
    status, body = _invoke(FakeRequest(method="GET", path="/", query={}))
    assert status == 400
    assert body["ok"] is False


def test_invalid_step_type_rejected(fake_tables):
    status, body = _invoke(FakeRequest(
        method="POST",
        path="/append",
        body={
            "request_id": "req-1",
            "step_type": "totally_made_up",
            "step_data": {},
        },
    ))
    assert status == 400
    assert body["error"] == "validation_failed"


def test_missing_request_id_on_append_rejected(fake_tables):
    status, body = _invoke(FakeRequest(
        method="POST",
        path="/append",
        body={"step_type": "input", "step_data": {}},
    ))
    assert status == 400
    assert body["error"] == "validation_failed"


# --------------------------------------------------------------------------- #
# Flag → bias review queue                                                    #
# --------------------------------------------------------------------------- #


def test_flag_writes_to_bias_review_queue(fake_tables):
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    # Seed the audit chain so the user_flag step can attach to something.
    _invoke(FakeRequest(
        method="POST",
        path="/append",
        body={
            "request_id": request_id,
            "step_type": "output",
            "step_data": {"answer": "12 incidents"},
        },
    ))

    status, body = _invoke(FakeRequest(
        method="POST",
        path="/flag",
        body={
            "request_id": request_id,
            "reason": "answer cites a station outside the queried district",
            "user_id": "officer-42",
        },
    ))
    assert status == 200, body
    assert body["ok"] is True
    assert body["queue"] == index.BIAS_REVIEW_TABLE
    assert body["status"] == "pending"
    flag_id = body["flag_id"]
    assert flag_id.startswith("flag-")

    # The queue row exists and has the expected schema.
    queue = fake_tables.get(index.BIAS_REVIEW_TABLE)
    assert len(queue._items) == 1
    row = queue._items[0]
    assert row["request_id"] == request_id
    assert row["user_id"] == "officer-42"
    assert row["status"] == "pending"
    assert row["reason"].startswith("answer cites")
    assert row["reviewer_id"] is None
    assert row["reviewer_notes"] is None

    # And a user_flag step was appended to the audit chain.
    status, fetch_body = _invoke(FakeRequest(
        method="GET",
        path="/",
        query={"request_id": request_id},
    ))
    assert status == 200
    step_types = [s["step_type"] for s in fetch_body["chain"]]
    assert "user_flag" in step_types


def test_flag_validation_rejects_empty_reason(fake_tables):
    status, body = _invoke(FakeRequest(
        method="POST",
        path="/flag",
        body={
            "request_id": "req-1",
            "reason": "",
            "user_id": "officer-1",
        },
    ))
    assert status == 400
    assert body["error"] == "validation_failed"


# --------------------------------------------------------------------------- #
# Concurrency — appends must not lose data                                    #
# --------------------------------------------------------------------------- #


def test_concurrent_appends_do_not_lose_data(fake_tables):
    """Hammer /append with 20 concurrent writes, then fetch.

    The function uses a read+write step_index allocator (no server-side
    atomic counter), so under contention two writers could pick the same
    step_index. Our contract is: every write must persist (no data
    loss), and the chain must remain readable. Duplicate step_indexes
    are tolerated and de-duplicated at fetch time.
    """
    request_id = f"race-{uuid.uuid4().hex[:8]}"
    n = 20

    def _append(i: int):
        return _invoke(FakeRequest(
            method="POST",
            path="/append",
            body={
                "request_id": request_id,
                "step_type": "tool_call",
                "step_data": {"tool": f"t{i}", "latency_ms": 10 + i},
            },
        ))

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_append, range(n)))

    # Every concurrent write returned 200 (no data loss).
    for status, body in results:
        assert status == 200, body
        assert body["ok"] is True

    # The underlying table has exactly n rows — proves no append was dropped.
    audit_table = fake_tables.get(index.AUDIT_TABLE)
    rows_for_req = [r for r in audit_table._items if r["request_id"] == request_id]
    assert len(rows_for_req) == n, (
        f"expected {n} rows persisted, got {len(rows_for_req)} — data was lost"
    )

    # And every appended tool name is present — proves no payload was overwritten.
    tools_present = {r["step_data"]["tool"] for r in rows_for_req}
    assert tools_present == {f"t{i}" for i in range(n)}

    # Fetch returns a coherent chain.
    status, body = _invoke(FakeRequest(
        method="GET",
        path="/",
        query={"request_id": request_id},
    ))
    assert status == 200
    assert body["ok"] is True
    # Chain may be <= n because duplicates on step_index are merged.
    assert 1 <= len(body["chain"]) <= n


# --------------------------------------------------------------------------- #
# Response envelope                                                           #
# --------------------------------------------------------------------------- #


def test_response_envelope_contains_service_and_region(fake_tables):
    status, body = _invoke(FakeRequest(
        method="POST",
        path="/append",
        body={
            "request_id": "req-envelope",
            "step_type": "input",
            "step_data": {"text": "test"},
        },
    ))
    assert status == 200
    assert body["service"] == index.SERVICE_NAME
    assert body["region"] == "IN"
    assert body["version"] == index.APP_VERSION
    assert body["timestamp_utc"].endswith("Z")
    assert isinstance(body["latency_ms"], int)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
