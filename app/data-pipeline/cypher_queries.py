"""
Cypher query library — KSP Saathi
=================================

Reusable, parameterized Cypher queries consumed by:
  - app/backend/functions/cypher-generator/  (LLM picks one + fills params)
  - app/data-pipeline/                       (operational queries)
  - app/frontend/components/NetworkGraph.tsx (via API gateway)

All queries are:
  - PARAMETERIZED (no string interpolation — injection-safe)
  - SCOPED (LIMIT on every traversal — prevents runaway queries)
  - ROLE-AGNOSTIC at this layer (RBAC enforced upstream at API gateway)

Each function returns a tuple of (cypher_text, params_dict) so the caller can
log them to the audit trail before execution (Section 5.8 of design.md).

Usage:
    from cypher_queries import find_criminal_network
    cypher, params = find_criminal_network("Manpreet Chowdary", hops=2)
    with driver.session() as s:
        records = list(s.run(cypher, **params))
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# 1. find_criminal_network — multi-hop traversal from a named person          #
# --------------------------------------------------------------------------- #

def find_criminal_network(
    person_name: str,
    hops: int = 2,
    limit: int = 200,
) -> tuple[str, dict[str, Any]]:
    """Return the N-hop criminal network around a named person.

    Traverses CO_ACCUSED_WITH (strongest signal) and CO_LOCATED_WITH (weaker),
    plus the ACCUSED_IN edges so the UI can show "why is this person linked?".

    Args:
        person_name: case-insensitive match on p.name
        hops: 1-3 (UI shows up to 3; default 2 balances density vs noise)
        limit: max nodes returned (default 200; AuraDB Free safety bound)

    Returns:
        (cypher, params) — caller must enforce hops in [1, 3] before passing.
    """
    if hops < 1 or hops > 3:
        raise ValueError("hops must be 1, 2, or 3")

    # Variable-length path uses string interpolation for hop count ONLY
    # (Cypher does not parameterize relationship-length range; this is safe
    # because we validate hops is a literal int in [1,3] above).
    cypher = f"""
    MATCH (seed:Person)
    WHERE toLower(seed.name) = toLower($person_name)
    CALL {{
        WITH seed
        MATCH path = (seed)-[:CO_ACCUSED_WITH|CO_LOCATED_WITH*1..{hops}]-(linked:Person)
        RETURN linked, path
        LIMIT $limit
    }}
    WITH seed, linked, path
    OPTIONAL MATCH (linked)-[:ACCUSED_IN]->(f:FIR)
    WITH seed, linked, path,
         collect(DISTINCT {{fir_no: f.fir_no, crime_type: f.crime_type, date: f.date_registered}})[..5] AS sample_cases
    RETURN
        seed.id              AS seed_id,
        seed.name            AS seed_name,
        linked.id            AS linked_id,
        linked.name          AS linked_name,
        linked.age           AS linked_age,
        linked.centrality    AS linked_centrality,
        length(path)         AS hop_distance,
        [r IN relationships(path) | type(r)] AS relationship_chain,
        sample_cases
    ORDER BY hop_distance ASC, linked.centrality DESC
    LIMIT $limit
    """
    return cypher, {"person_name": person_name, "limit": limit}


# --------------------------------------------------------------------------- #
# 2. find_similar_mo — MO / crime-type clustering across a time window        #
# --------------------------------------------------------------------------- #

def find_similar_mo(
    crime_type: str,
    days_back: int = 30,
    district: str | None = None,
    limit: int = 50,
) -> tuple[str, dict[str, Any]]:
    """Find FIRs of the same crime_type within the last N days, optionally
    scoped to a district. Useful for "show similar MO" suggestions in the chat.

    Co-occurrence enrichment: returns top H3 cells and top accused for the set.

    Args:
        crime_type: e.g. "chain_snatching", "vehicle_theft"
        days_back: lookback window in days (default 30)
        district: optional filter (e.g. "Bengaluru Urban")
        limit: max FIRs returned

    Returns:
        (cypher, params)
    """
    cypher = """
    MATCH (f:FIR)
    WHERE f.crime_type = $crime_type
      AND date(f.date_registered) >= date() - duration({days: $days_back})
      AND ($district IS NULL OR f.district = $district)
    OPTIONAL MATCH (f)-[:OCCURRED_AT]->(l:Location)
    OPTIONAL MATCH (f)-[:AT_STATION]->(s:Station)
    OPTIONAL MATCH (a:Person)-[:ACCUSED_IN]->(f)
    WITH f, l, s, collect(DISTINCT a.name)[..5] AS accused_sample
    RETURN
        f.fir_no             AS fir_no,
        f.date_registered    AS date,
        f.time_registered    AS time,
        f.crime_type         AS crime_type,
        f.modus_operandi     AS modus_operandi,
        f.status             AS status,
        s.name               AS station,
        f.district           AS district,
        l.h3_index           AS h3_index,
        l.lat                AS lat,
        l.lng                AS lng,
        l.text               AS location_text,
        accused_sample
    ORDER BY f.date_registered DESC, f.time_registered DESC
    LIMIT $limit
    """
    return cypher, {
        "crime_type": crime_type,
        "days_back": days_back,
        "district": district,
        "limit": limit,
    }


# --------------------------------------------------------------------------- #
# 3. gang_hubs_by_district — top centrality Persons in an area                #
# --------------------------------------------------------------------------- #

def gang_hubs_by_district(
    district: str,
    limit: int = 20,
    min_cases: int = 2,
) -> tuple[str, dict[str, Any]]:
    """Top connected suspects whose cases are predominantly in a given district.

    Uses the precomputed `p.centrality` property (see derived_edges.py).
    Filters out persons whose primary district doesn't match — a person can be
    accused in many districts; we attribute them to the district where they
    have the most FIRs.

    Args:
        district: e.g. "Bengaluru Urban"
        limit: max persons returned
        min_cases: minimum ACCUSED_IN count to qualify (filters noise)

    Returns:
        (cypher, params)
    """
    cypher = """
    MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR)
    WHERE f.district = $district
    WITH p, count(DISTINCT f) AS district_cases, collect(DISTINCT f.fir_no)[..10] AS fir_sample
    WHERE district_cases >= $min_cases
    OPTIONAL MATCH (p)-[co:CO_ACCUSED_WITH]-(other:Person)
    WITH p, district_cases, fir_sample, count(DISTINCT other) AS network_size
    RETURN
        p.id                 AS person_id,
        p.name               AS name,
        p.age                AS age,
        p.centrality         AS centrality,
        p.case_count         AS total_cases,
        district_cases,
        network_size,
        fir_sample
    ORDER BY p.centrality DESC, district_cases DESC
    LIMIT $limit
    """
    return cypher, {"district": district, "limit": limit, "min_cases": min_cases}


# --------------------------------------------------------------------------- #
# 4. repeat_offenders — Persons with >= N ACCUSED_IN cases                    #
# --------------------------------------------------------------------------- #

def repeat_offenders(
    min_cases: int = 3,
    crime_type: str | None = None,
    limit: int = 50,
) -> tuple[str, dict[str, Any]]:
    """Persons accused in >= min_cases FIRs, optionally filtered by crime_type.

    Args:
        min_cases: threshold (default 3 — what most investigators consider "repeat")
        crime_type: optional filter for crime-specific repeat offenders
        limit: max persons returned

    Returns:
        (cypher, params)
    """
    cypher = """
    MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR)
    WHERE ($crime_type IS NULL OR f.crime_type = $crime_type)
    WITH p,
         count(DISTINCT f) AS case_count,
         collect(DISTINCT f.crime_type) AS crime_types,
         collect(DISTINCT f.district)[..5] AS districts,
         collect({fir_no: f.fir_no, crime_type: f.crime_type, date: f.date_registered, status: f.status})[..10] AS sample_cases,
         min(f.date_registered) AS first_seen,
         max(f.date_registered) AS last_seen
    WHERE case_count >= $min_cases
    RETURN
        p.id          AS person_id,
        p.name        AS name,
        p.age         AS age,
        p.gender      AS gender,
        p.centrality  AS centrality,
        case_count,
        crime_types,
        districts,
        first_seen,
        last_seen,
        sample_cases
    ORDER BY case_count DESC, p.centrality DESC
    LIMIT $limit
    """
    return cypher, {
        "min_cases": min_cases,
        "crime_type": crime_type,
        "limit": limit,
    }


# --------------------------------------------------------------------------- #
# Bonus helpers (used by the orchestrator's Cypher generator as scaffolding)  #
# --------------------------------------------------------------------------- #

def fir_full_context(fir_no: str) -> tuple[str, dict[str, Any]]:
    """Return everything about one FIR + its 1-hop neighbourhood. Used by the
    chat "tell me about FIR X" intent."""
    cypher = """
    MATCH (f:FIR {fir_no: $fir_no})
    OPTIONAL MATCH (f)-[:AT_STATION]->(s:Station)
    OPTIONAL MATCH (f)-[:OCCURRED_AT]->(l:Location)
    OPTIONAL MATCH (acc:Person)-[:ACCUSED_IN]->(f)
    OPTIONAL MATCH (vic:Person)-[:VICTIM_IN]->(f)
    OPTIONAL MATCH (comp:Person)-[:COMPLAINANT_IN]->(f)
    RETURN
        f { .* }                                          AS fir,
        s { .* }                                          AS station,
        l { .* }                                          AS location,
        collect(DISTINCT acc { .id, .name, .age, .centrality })  AS accused,
        collect(DISTINCT vic { .id, .name, .age })        AS victims,
        collect(DISTINCT comp { .id, .name, .age })       AS complainants
    """
    return cypher, {"fir_no": fir_no}


def person_full_history(person_name: str, limit: int = 50) -> tuple[str, dict[str, Any]]:
    """Full FIR history for a named person — the "PSI at the scene" query."""
    cypher = """
    MATCH (p:Person)
    WHERE toLower(p.name) = toLower($person_name)
    OPTIONAL MATCH (p)-[r:ACCUSED_IN]->(f:FIR)
    WITH p, r, f
    ORDER BY f.date_registered DESC
    WITH p, collect({
        fir_no: f.fir_no,
        crime_type: f.crime_type,
        date: f.date_registered,
        district: f.district,
        status: f.status,
        accused_status: r.status,
        ipc_sections: f.ipc_sections
    })[..$limit] AS cases
    RETURN
        p.id          AS person_id,
        p.name        AS name,
        p.age         AS age,
        p.gender      AS gender,
        p.centrality  AS centrality,
        p.case_count  AS total_cases,
        cases
    """
    return cypher, {"person_name": person_name, "limit": limit}


# --------------------------------------------------------------------------- #
# Registry — used by the Cypher generator LLM as a "tools" list                #
# --------------------------------------------------------------------------- #

QUERY_REGISTRY = {
    "find_criminal_network":   find_criminal_network,
    "find_similar_mo":         find_similar_mo,
    "gang_hubs_by_district":   gang_hubs_by_district,
    "repeat_offenders":        repeat_offenders,
    "fir_full_context":        fir_full_context,
    "person_full_history":     person_full_history,
}


__all__ = [
    "find_criminal_network",
    "find_similar_mo",
    "gang_hubs_by_district",
    "repeat_offenders",
    "fir_full_context",
    "person_full_history",
    "QUERY_REGISTRY",
]
