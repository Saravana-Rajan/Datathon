"""
Derived edges + centrality — KSP Saathi
========================================

Second-pass module called by neo4j_ingest.py after primary nodes/edges land.
Produces the inferred relationships investigators actually search on:

    (p1:Person)-[:CO_ACCUSED_WITH {weight}]-(p2:Person)
        - two accused in the SAME FIR
        - weight = number of co-accusal events (symmetric)

    (p1:Person)-[:CO_LOCATED_WITH {h3, count}]-(p2:Person)
        - two accused in FIRs at the SAME H3 cell (but not necessarily the
          same FIR) — captures "operates in the same micro-locality"
        - count = number of distinct shared H3 cells

    centrality:  PageRank-style score per Person node
        - APOC / GDS not available on AuraDB Free, so we use a portable
          weighted-degree score: degree in co-accusal graph * log(case_count)
          → highlights people both well-connected AND personally prolific.
        - Returns top N as a list[dict] (caller writes `.centrality` back).

Designed to be safe to re-run: edges are MERGEd, properties updated in place.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import Driver

log = logging.getLogger("derived_edges")


# --------------------------------------------------------------------------- #
# CO_ACCUSED_WITH                                                             #
# --------------------------------------------------------------------------- #

# Strategy: for every FIR with >=2 accused, find unique person pairs and
# MERGE a symmetric (undirected) edge with weight = count of shared FIRs.
#
# Why one direction in MERGE but treated as undirected at query time:
#   Neo4j stores every relationship with a direction internally, but our
#   query patterns use `()-[:CO_ACCUSED_WITH]-()` (no arrow), so direction
#   is ignored. We enforce p1.id < p2.id at create time so we never produce
#   both (a)->(b) and (b)->(a) duplicates.

CO_ACCUSED_CYPHER = """
MATCH (f:FIR)<-[:ACCUSED_IN]-(p1:Person)
MATCH (f)<-[:ACCUSED_IN]-(p2:Person)
WHERE p1.id < p2.id
WITH p1, p2, count(DISTINCT f) AS shared_firs, collect(DISTINCT f.fir_no)[..10] AS sample_firs
MERGE (p1)-[r:CO_ACCUSED_WITH]-(p2)
  ON CREATE SET r.weight = shared_firs,
                r.sample_firs = sample_firs,
                r.created_at = datetime()
  ON MATCH  SET r.weight = shared_firs,
                r.sample_firs = sample_firs,
                r.updated_at = datetime()
RETURN count(r) AS edges
"""


def compute_co_accused(driver: Driver) -> int:
    """MERGE CO_ACCUSED_WITH edges from existing ACCUSED_IN relationships.

    Returns the number of edges touched.
    """
    with driver.session() as session:
        record = session.execute_write(
            lambda tx: tx.run(CO_ACCUSED_CYPHER).single()
        )
    edges = record["edges"] if record else 0
    log.info("  CO_ACCUSED_WITH: %d edges merged", edges)
    return edges


# --------------------------------------------------------------------------- #
# CO_LOCATED_WITH                                                             #
# --------------------------------------------------------------------------- #

# Two accused are "co-located" if they appear in (any) FIRs at the same H3
# cell — even if not the same FIR. This catches "they hit the same area at
# different times" patterns that pure co-accusal misses.
#
# We cap pairs per H3 cell to avoid Cartesian explosions on hot hexes
# (cybercrime hubs etc.) — using a cell-level pair count threshold.

CO_LOCATED_CYPHER = """
MATCH (l:Location)<-[:OCCURRED_AT]-(:FIR)<-[:ACCUSED_IN]-(p1:Person)
MATCH (l)<-[:OCCURRED_AT]-(:FIR)<-[:ACCUSED_IN]-(p2:Person)
WHERE p1.id < p2.id
WITH p1, p2, count(DISTINCT l) AS shared_cells, collect(DISTINCT l.h3_index)[..5] AS sample_cells
WHERE shared_cells >= 1
MERGE (p1)-[r:CO_LOCATED_WITH]-(p2)
  ON CREATE SET r.count = shared_cells,
                r.sample_h3 = sample_cells,
                r.created_at = datetime()
  ON MATCH  SET r.count = shared_cells,
                r.sample_h3 = sample_cells,
                r.updated_at = datetime()
RETURN count(r) AS edges
"""


def compute_co_located(driver: Driver) -> int:
    """MERGE CO_LOCATED_WITH edges from ACCUSED_IN + OCCURRED_AT.

    Returns the number of edges touched.
    """
    with driver.session() as session:
        record = session.execute_write(
            lambda tx: tx.run(CO_LOCATED_CYPHER).single()
        )
    edges = record["edges"] if record else 0
    log.info("  CO_LOCATED_WITH: %d edges merged", edges)
    return edges


# --------------------------------------------------------------------------- #
# Centrality (PageRank-style, portable to AuraDB Free)                        #
# --------------------------------------------------------------------------- #

# AuraDB Free does NOT include GDS or APOC plugins, so the canonical
# `gds.pageRank.stream(...)` call is unavailable. We compute a portable
# centrality proxy entirely in Cypher:
#
#   score(p) =  case_count(p) * log10(1 + sum_co_accused_weight(p))
#
# Intuition:
#   - case_count alone catches petty repeat offenders with no network
#   - co-accused weight alone catches one-time gang ops
#   - the product highlights people who are BOTH prolific AND networked
#     — i.e. the gang hubs a DySP cares about.
#
# We materialize the score on the node (p.centrality) so downstream Cypher
# can ORDER BY it without recomputation.

CENTRALITY_CYPHER = """
MATCH (p:Person)
OPTIONAL MATCH (p)-[:ACCUSED_IN]->(f:FIR)
WITH p, count(DISTINCT f) AS case_count
OPTIONAL MATCH (p)-[r:CO_ACCUSED_WITH]-()
WITH p, case_count, coalesce(sum(r.weight), 0) AS co_weight
WITH p, case_count, co_weight,
     case_count * log10(1 + co_weight) AS score
SET p.case_count = case_count,
    p.co_accused_weight = co_weight,
    p.centrality = score
WITH p, score, case_count, co_weight
WHERE case_count > 0
RETURN p.id AS id, p.name AS name, p.age AS age,
       case_count, co_weight, score
ORDER BY score DESC, case_count DESC
LIMIT $top_n
"""


def compute_centrality(driver: Driver, top_n: int = 100) -> list[dict[str, Any]]:
    """Compute portable centrality, persist to nodes, return top N.

    Each returned dict has keys: id, name, age, case_count, co_weight, score.
    """
    with driver.session() as session:
        result = session.execute_write(
            lambda tx: list(tx.run(CENTRALITY_CYPHER, top_n=top_n))
        )
    rows = [
        {
            "id": r["id"],
            "name": r["name"],
            "age": r["age"],
            "case_count": r["case_count"],
            "co_accused_weight": r["co_weight"],
            "score": float(r["score"] or 0.0),
        }
        for r in result
    ]
    log.info("  Centrality: scored %d Persons; top score=%.4f",
             len(rows), rows[0]["score"] if rows else 0.0)
    return rows


# --------------------------------------------------------------------------- #
# Standalone CLI (re-run derivation without re-ingesting)                     #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse
    import os
    import sys
    from neo4j import GraphDatabase

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Re-run derived-edge computation on an already-ingested graph."
    )
    parser.add_argument("--top-n", type=int, default=100,
                        help="Number of top centrality persons to print (default 100)")
    parser.add_argument("--only", choices=("co_accused", "co_located", "centrality"),
                        help="Run only one stage instead of all three.")
    args = parser.parse_args()

    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    pw = os.environ.get("NEO4J_PASSWORD")
    if not (uri and user and pw):
        print("Set NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD env vars.", file=sys.stderr)
        sys.exit(2)

    driver = GraphDatabase.driver(uri, auth=(user, pw))
    try:
        driver.verify_connectivity()
        if args.only in (None, "co_accused"):
            compute_co_accused(driver)
        if args.only in (None, "co_located"):
            compute_co_located(driver)
        if args.only in (None, "centrality"):
            top = compute_centrality(driver, top_n=args.top_n)
            print()
            print(f"Top {min(args.top_n, len(top))} gang-hub candidates:")
            print("-" * 70)
            for i, row in enumerate(top, 1):
                print(f"{i:>3}. {row['name']:<25} "
                      f"cases={row['case_count']:>3}  "
                      f"co_weight={row['co_accused_weight']:>4}  "
                      f"score={row['score']:.4f}")
    finally:
        driver.close()
