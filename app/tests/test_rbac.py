"""Role-based access control tests for Sarvik.

The 9th feature in the Challenge 01 problem statement is *Role-based
secure access*. This test module captures the contract we promise:

* A **PSI** sees only FIRs from their own station, and gets PII heavily
  masked (phone, address, victim name).
* An **SHO** (Inspector running a station) sees their station's FIRs,
  with lighter masking (phone still masked).
* A **DCP** sees all FIRs in their district, no masking.
* Every read is recorded by the audit logger with the actor's ID.

We don't depend on the real Catalyst Auth here — the ``test_user_token``
factory mints role-bearing tokens that the in-test scope-filter and
PII-masker logic can interpret. The same logic ships in
``shared/rbac.py`` in production; the test reimplements it in-line so
the assertions document the contract precisely.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Iterable

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.rbac]


# ---------------------------------------------------------------------------
# Reference RBAC implementation — mirrors what shared/rbac.py exposes.
# Kept in this file so the tests are the canonical contract.
# ---------------------------------------------------------------------------

def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            return [
                _get_path(item, ".".join(path.split(".")[1:]))
                for item in cur
            ]
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _mask_path(obj: dict, path: str) -> None:
    """In-place: replace the leaf at ``path`` with the string ``'***MASKED***'``.

    Handles list nodes by recursing into each element.
    """
    parts = path.split(".")
    cur: Any = obj
    for part in parts[:-1]:
        if isinstance(cur, list):
            for item in cur:
                _mask_path(item, ".".join(parts[parts.index(part):]))
            return
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    leaf = parts[-1]
    if isinstance(cur, list):
        for item in cur:
            if isinstance(item, dict) and leaf in item:
                item[leaf] = "***MASKED***"
        return
    if isinstance(cur, dict) and leaf in cur:
        cur[leaf] = "***MASKED***"


def filter_for_role(records: Iterable[dict], claims: dict) -> list[dict]:
    """Apply the scope filter + masking rules implied by the token claims."""
    scope = claims.get("scope")
    station = claims.get("station")
    district = claims.get("district")
    masked_fields = claims.get("masked_fields") or []

    out: list[dict] = []
    for rec in records:
        if scope == "station":
            if station and rec.get("station_name") != station:
                continue
        elif scope == "district":
            if district and rec.get("district") != district:
                continue
        elif scope == "state":
            pass  # no filter
        else:
            # Unknown scope = deny by default (fail-closed).
            continue

        # Deep-copy so we don't mutate the source corpus.
        copy_rec = copy.deepcopy(rec)
        for path in masked_fields:
            _mask_path(copy_rec, path)
        out.append(copy_rec)
    return out


# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------

@pytest.fixture
def rbac_corpus() -> list[dict]:
    """6 FIRs spanning two districts and three stations.

    Mirrors the shape of records in ``data/firs_sample.jsonl`` but is
    hand-built so we can pin exact assertions about who sees what.
    """
    return [
        {
            "fir_no": "MGR/2025/00001",
            "station_name": "MG Road Police Station",
            "district": "Bengaluru Urban",
            "complainant": {
                "name": "Manjunath Babu", "age": 40, "gender": "M",
                "phone": "78XXXXXX26",
                "address": "#349, 9th Cross, ITPL Road, Bengaluru Urban - 560017",
            },
            "victims": [{"name": "Manjunath Babu", "age": 40, "gender": "M"}],
            "crime_type": "burglary",
        },
        {
            "fir_no": "MGR/2025/00002",
            "station_name": "MG Road Police Station",
            "district": "Bengaluru Urban",
            "complainant": {
                "name": "Asha R", "age": 32, "gender": "F",
                "phone": "98XXXXXX12",
                "address": "#22, Brigade Road, Bengaluru Urban - 560001",
            },
            "victims": [{"name": "Asha R", "age": 32, "gender": "F"}],
            "crime_type": "theft",
        },
        {
            "fir_no": "HAL/2024/00007",
            "station_name": "Halasuru Police Station",
            "district": "Bengaluru Urban",
            "complainant": {
                "name": "Prakash S", "age": 27, "gender": "M",
                "phone": "78XXXXXX35",
                "address": "Richmond Road, Bengaluru Urban - 572101",
            },
            "victims": [{"name": "Prakash S", "age": 27, "gender": "M"}],
            "crime_type": "cybercrime",
        },
        {
            "fir_no": "DEV/2024/00001",
            "station_name": "Devaraja Police Station",
            "district": "Mysuru",
            "complainant": {
                "name": "Mohsin N", "age": 54, "gender": "M",
                "phone": "83XXXXXX18",
                "address": "Saraswathipuram, Mysuru - 580001",
            },
            "victims": [{"name": "Bharathi S", "age": 61, "gender": "F"}],
            "crime_type": "vehicle_theft",
        },
        {
            "fir_no": "DEV/2024/00009",
            "station_name": "Devaraja Police Station",
            "district": "Mysuru",
            "complainant": {
                "name": "Rajesh K", "age": 45, "gender": "M",
                "phone": "91XXXXXX99",
                "address": "Vijayanagar, Mysuru - 580001",
            },
            "victims": [{"name": "Rajesh K", "age": 45, "gender": "M"}],
            "crime_type": "fraud",
        },
        {
            "fir_no": "KHAB/2023/00001",
            "station_name": "Khade Bazar Police Station",
            "district": "Belagavi",
            "complainant": {
                "name": "Murthy J", "age": 52, "gender": "M",
                "phone": "91XXXXXX16",
                "address": "Shahapur, Belagavi - 560095",
            },
            "victims": [{"name": "Murthy J", "age": 52, "gender": "M"}],
            "crime_type": "vehicle_theft",
        },
    ]


# ---------------------------------------------------------------------------
# Scope: PSI sees only own station
# ---------------------------------------------------------------------------

def test_psi_only_sees_own_station(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("PSI")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)

    # PSI is assigned to MG Road Police Station per conftest.
    stations = {r["station_name"] for r in visible}
    assert stations == {"MG Road Police Station"}, (
        f"PSI saw stations outside scope: {stations}"
    )
    fir_nos = {r["fir_no"] for r in visible}
    assert fir_nos == {"MGR/2025/00001", "MGR/2025/00002"}, fir_nos


def test_sho_only_sees_own_station(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("SHO")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)
    stations = {r["station_name"] for r in visible}
    assert stations == {"MG Road Police Station"}


def test_dcp_sees_whole_district(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("DCP")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)

    # DCP fixture is for Bengaluru Urban — must see MG Road + Halasuru
    # but NOT Mysuru / Belagavi.
    districts = {r["district"] for r in visible}
    assert districts == {"Bengaluru Urban"}, districts
    stations = {r["station_name"] for r in visible}
    assert "MG Road Police Station" in stations
    assert "Halasuru Police Station" in stations
    assert "Devaraja Police Station" not in stations
    assert "Khade Bazar Police Station" not in stations


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------

def test_psi_sees_phone_address_and_victim_name_masked(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("PSI")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)
    assert visible, "PSI got an empty result set"
    for rec in visible:
        assert rec["complainant"]["phone"] == "***MASKED***", rec["complainant"]
        assert rec["complainant"]["address"] == "***MASKED***", rec["complainant"]
        for v in rec["victims"]:
            assert v["name"] == "***MASKED***", v
        # Complainant name remains visible to PSI (they need to call them).
        assert rec["complainant"]["name"] not in (None, "", "***MASKED***")


def test_sho_sees_phone_masked_but_address_visible(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("SHO")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)
    assert visible
    for rec in visible:
        assert rec["complainant"]["phone"] == "***MASKED***", rec["complainant"]
        # Address is needed by SHO for scene visits — visible.
        assert "MASKED" not in (rec["complainant"]["address"] or "")
        # Victim names visible to SHO.
        for v in rec["victims"]:
            assert v["name"] != "***MASKED***", v


def test_dcp_sees_unmasked_data(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
) -> None:
    token = test_user_token("DCP")
    claims = mock_rbac_decode(token)
    visible = filter_for_role(rbac_corpus, claims)
    assert visible
    for rec in visible:
        assert "MASKED" not in (rec["complainant"]["phone"] or "")
        assert "MASKED" not in (rec["complainant"]["address"] or "")
        for v in rec["victims"]:
            assert v["name"] != "***MASKED***"


# ---------------------------------------------------------------------------
# Audit logging — every read records the actor
# ---------------------------------------------------------------------------

def _record_read(
    claims: dict,
    records: list[dict],
    client,
    *,
    purpose: str = "query",
) -> list[dict]:
    """Read through the audited path: filter, then append one audit row."""
    visible = filter_for_role(records, claims)
    client.append_audit({
        "step_type": "data_read",
        "actor_id": claims.get("sub"),
        "actor_role": claims.get("role"),
        "scope": claims.get("scope"),
        "purpose": purpose,
        "record_count": len(visible),
        "fir_nos": [r["fir_no"] for r in visible],
    })
    return visible


def test_audit_log_records_actor_for_every_read(
    rbac_corpus: list[dict],
    test_user_token: Callable[[str], str],
    mock_rbac_decode: Callable[[str], dict],
    mock_catalyst_client,
) -> None:
    """Three different role reads should produce three audit entries.

    Each entry must capture: actor id, role, scope, purpose, count, and
    the specific FIR numbers returned. This is the chain that powers the
    "Why?" drawer for explainability.
    """
    for role, expected_count in (("PSI", 2), ("SHO", 2), ("DCP", 3)):
        token = test_user_token(role)
        claims = mock_rbac_decode(token)
        visible = _record_read(claims, rbac_corpus, mock_catalyst_client)
        assert len(visible) == expected_count, (
            f"{role} expected {expected_count} records, got {len(visible)}"
        )

    # Exactly 3 audit entries — one per read.
    assert len(mock_catalyst_client.audit_chain) == 3, mock_catalyst_client.audit_chain

    # Each entry must carry the role-bearing actor.
    actor_roles = [
        a["actor_role"] for a in mock_catalyst_client.audit_chain
    ]
    assert actor_roles == ["sub_inspector", "inspector", "dcp"], actor_roles

    # Each entry must carry a non-empty actor id.
    for entry in mock_catalyst_client.audit_chain:
        assert entry["actor_id"], f"audit entry missing actor_id: {entry}"
        assert entry["step_type"] == "data_read"
        assert entry["scope"] in {"station", "district", "state"}
        assert isinstance(entry["fir_nos"], list)


def test_unknown_role_denied_by_default(
    rbac_corpus: list[dict],
) -> None:
    """An unknown scope (typo, expired token, …) must fail closed — zero rows."""
    claims = {"sub": "u-x", "role": "constable", "scope": "unspecified"}
    visible = filter_for_role(rbac_corpus, claims)
    assert visible == [], visible
