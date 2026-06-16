"""
Unit tests for the KSP Saathi hello smoke-test function.

These tests do NOT require the Catalyst SDK to be installed — the handler is
designed to degrade gracefully when the SDK is absent (it reports the import
failure in the response body but still returns a valid 200 payload). That lets
us run these tests in any CI environment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make the function module importable without installing it as a package.
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import index  # noqa: E402  — path manipulation above is intentional


# --------------------------------------------------------------------------- #
# Fakes that mimic Catalyst Advanced I/O request/response objects.            #
# --------------------------------------------------------------------------- #


class FakeRequest:
    """Mimics the subset of the Catalyst request object the handler reads."""

    def __init__(self, query: dict[str, str] | None = None):
        self.args = query or {}
        self.query_params = self.args


class FakeResponse:
    """Captures status + body so tests can assert on them."""

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


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


def _invoke(query: dict[str, str] | None = None) -> dict:
    req = FakeRequest(query=query)
    res = FakeResponse()
    context = MagicMock()
    basic_io = FakeBasicIO(req, res)

    result = index.handler(context, basic_io)
    assert isinstance(result, dict), "handler must return the response body for testability"
    assert res.status == 200, f"expected 200, got {res.status}; body={res.body}"
    assert res.body is not None
    parsed = json.loads(res.body)
    assert parsed == result, "response.send body and return value must match"
    return result


def test_returns_both_kannada_and_english_greetings():
    body = _invoke({"name": "Asha"})

    assert body["ok"] is True
    greeting = body["greeting"]

    # Kannada greeting must contain the Devanagari/Kannada-script word ನಮಸ್ಕಾರ.
    assert "ನಮಸ್ಕಾರ" in greeting["kannada"], f"missing Kannada script: {greeting}"
    assert "Asha" in greeting["kannada"]

    # English greeting must contain "Hello".
    assert "Hello" in greeting["english"], f"missing English greeting: {greeting}"
    assert "Asha" in greeting["english"]


def test_region_is_india():
    body = _invoke()
    assert body["region"] == "IN", "Catalyst India DC is mandatory (IT Act 2008)"


def test_defaults_when_no_name_provided():
    body = _invoke()
    assert body["name"] == "investigator"
    assert "investigator" in body["greeting"]["english"]
    assert "investigator" in body["greeting"]["kannada"]


def test_version_and_timestamp_present():
    body = _invoke()
    assert body["version"] == index.APP_VERSION
    assert body["timestamp_utc"].endswith("Z")
    assert "T" in body["timestamp_utc"]


def test_env_diagnostic_redacts_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-do-not-leak")
    monkeypatch.delenv("NEO4J_URI", raising=False)

    body = _invoke()
    diag = body["env_diagnostic"]

    assert diag["GEMINI_API_KEY"] == "set"
    assert diag["NEO4J_URI"] == "unset"
    # The actual secret must never appear in the payload.
    assert "super-secret-do-not-leak" not in json.dumps(body)


def test_catalyst_sdk_status_reported():
    body = _invoke()
    sdk = body["catalyst_sdk"]
    # We don't require the SDK to be installed/initialised in tests — we only
    # require the diagnostic shape to be correct so monitoring can read it.
    assert set(sdk.keys()) == {"sdk_imported", "sdk_initialized", "nosql_reachable", "error"}
    assert isinstance(sdk["sdk_imported"], bool)
    assert isinstance(sdk["sdk_initialized"], bool)
    assert isinstance(sdk["nosql_reachable"], bool)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
