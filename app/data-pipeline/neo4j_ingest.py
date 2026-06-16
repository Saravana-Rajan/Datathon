"""
Neo4j Ingestion — KSP Saathi Criminal Network Graph
====================================================

Ingests synthetic FIR records (JSONL) into Neo4j AuraDB Free and builds the
criminal network graph used by Section 5.5 of the design doc.

Graph schema (locked):
    (p:Person {id, name, age, gender})
    (f:FIR {fir_no, crime_type, date_registered, status, ...})
    (s:Station {name, lat, lng, district})
    (l:Location {h3_index, h3_resolution, lat, lng})

    (p)-[:ACCUSED_IN]->(f)
    (p)-[:COMPLAINANT_IN]->(f)
    (p)-[:VICTIM_IN]->(f)
    (f)-[:AT_STATION]->(s)
    (f)-[:OCCURRED_AT]->(l)

Derived (computed by derived_edges.py after primary ingest):
    (p1)-[:CO_ACCUSED_WITH {weight}]-(p2)
    (p1)-[:CO_LOCATED_WITH {h3, count}]-(p2)

Person identity resolution:
    Real CCTNS data has NO unique accused ID across stations (see design.md
    Section 3 — DySP pain point). We use `lower(name) + "::" + age` as a soft
    key. This is intentionally lossy: it will under-merge (same person across
    age changes) and over-merge (different people with same name+age). The
    derived-edges pass and centrality model are designed to tolerate this.
    Documented in README.md "Known limitations".

Performance:
    Batched UNWIND, parameterized queries. ~30s for 5K rows, ~5min for 50K
    on AuraDB Free.

Usage:
    export NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
    export NEO4J_USER=neo4j
    export NEO4J_PASSWORD=<your-password>

    python neo4j_ingest.py --input ../data/firs.jsonl --limit 1000 --batch 500
    python neo4j_ingest.py --input ../data/firs.jsonl                 # full 50K
    python neo4j_ingest.py --input ../data/firs.jsonl --skip-derived  # primary only
    python neo4j_ingest.py --input ../data/firs.jsonl --reset         # wipe DB first
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

try:
    import h3
except ImportError:  # pragma: no cover
    print("Missing dependency: h3>=4.0.0  ->  pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    from neo4j import GraphDatabase, Driver
    from neo4j.exceptions import ServiceUnavailable, AuthError
except ImportError:  # pragma: no cover
    print("Missing dependency: neo4j>=5.18.0  ->  pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    print("Missing dependency: tqdm  ->  pip install -r requirements.txt", file=sys.stderr)
    raise


# H3 resolution 8 ≈ 0.7 km² hexagons — a reasonable "block-level" cell for
# linking accused who operate in the same micro-locality. Tweak per design.md.
H3_RESOLUTION = 8

# Names treated as identity-unknown (synthetic data uses "Unknown" placeholders).
UNKNOWN_NAME_TOKENS = {"unknown", "unidentified", "not known", "n/a", "na", ""}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("neo4j_ingest")


# --------------------------------------------------------------------------- #
# Identity resolution                                                         #
# --------------------------------------------------------------------------- #

def person_id(name: str | None, age: Any) -> str | None:
    """Soft identity key: lower(trimmed name) + "::" + age_or_x.

    Returns None for unknown / unusable names (we don't create Person nodes
    for them — they'd collapse the whole graph into one super-hub).
    """
    if not name:
        return None
    n = name.strip().lower()
    if n in UNKNOWN_NAME_TOKENS:
        return None
    age_part = str(int(age)) if isinstance(age, (int, float)) and age else "x"
    return f"{n}::{age_part}"


# --------------------------------------------------------------------------- #
# Record -> graph payloads                                                    #
# --------------------------------------------------------------------------- #

def build_payload(rec: dict) -> dict:
    """Transform one FIR record into the dict shape consumed by UNWIND queries.

    All persons (complainant, accused[], victims[]) share the same id-resolution
    rule, so the same human appearing in two roles across two FIRs gets merged
    into one (:Person) node with two outgoing relationships.
    """
    fir_no = rec["fir_no"]

    # ---- Station node ----
    station = {
        "name": rec["station_name"],
        "lat": rec.get("station_lat"),
        "lng": rec.get("station_lng"),
        "district": rec.get("district"),
    }

    # ---- Location node (H3-indexed) ----
    loc_lat = rec.get("location_lat")
    loc_lng = rec.get("location_lng")
    location: dict | None = None
    if loc_lat is not None and loc_lng is not None:
        h3_index = h3.latlng_to_cell(loc_lat, loc_lng, H3_RESOLUTION)
        location = {
            "h3_index": h3_index,
            "h3_resolution": H3_RESOLUTION,
            "lat": loc_lat,
            "lng": loc_lng,
            "text": rec.get("location_text"),
        }

    # ---- FIR node ----
    fir = {
        "fir_no": fir_no,
        "crime_type": rec.get("crime_type"),
        "date_registered": rec.get("date_registered"),
        "time_registered": rec.get("time_registered"),
        "status": rec.get("status"),
        "ipc_sections": rec.get("ipc_sections") or [],
        "district": rec.get("district"),
        "modus_operandi": rec.get("modus_operandi"),
        "narrative": rec.get("narrative"),
        "linked_fir_nos": rec.get("linked_fir_nos") or [],
    }

    # ---- Person rows (one per role-link) ----
    persons: list[dict] = []

    comp = rec.get("complainant") or {}
    pid = person_id(comp.get("name"), comp.get("age"))
    if pid:
        persons.append({
            "id": pid,
            "name": comp.get("name"),
            "age": comp.get("age"),
            "gender": comp.get("gender"),
            "phone": comp.get("phone"),
            "role": "COMPLAINANT_IN",
        })

    for acc in rec.get("accused") or []:
        pid = person_id(acc.get("name"), acc.get("age"))
        if pid:
            persons.append({
                "id": pid,
                "name": acc.get("name"),
                "age": acc.get("age"),
                "gender": acc.get("gender"),
                "status": acc.get("status"),
                "role": "ACCUSED_IN",
            })

    for vic in rec.get("victims") or []:
        pid = person_id(vic.get("name"), vic.get("age"))
        if pid:
            persons.append({
                "id": pid,
                "name": vic.get("name"),
                "age": vic.get("age"),
                "gender": vic.get("gender"),
                "relation": vic.get("relation_to_complainant"),
                "role": "VICTIM_IN",
            })

    return {
        "fir": fir,
        "station": station,
        "location": location,
        "persons": persons,
    }


def stream_jsonl(path: Path, limit: int | None) -> Iterator[dict]:
    n = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
            n += 1
            if limit and n >= limit:
                return


def batched(iterable: Iterable[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# --------------------------------------------------------------------------- #
# Cypher                                                                      #
# --------------------------------------------------------------------------- #

CONSTRAINTS = [
    "CREATE CONSTRAINT person_id_unique IF NOT EXISTS "
    "FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT fir_no_unique IF NOT EXISTS "
    "FOR (f:FIR) REQUIRE f.fir_no IS UNIQUE",
    "CREATE CONSTRAINT station_name_unique IF NOT EXISTS "
    "FOR (s:Station) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT location_h3_unique IF NOT EXISTS "
    "FOR (l:Location) REQUIRE l.h3_index IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
    "CREATE INDEX fir_crime_type IF NOT EXISTS FOR (f:FIR) ON (f.crime_type)",
    "CREATE INDEX fir_date IF NOT EXISTS FOR (f:FIR) ON (f.date_registered)",
    "CREATE INDEX fir_district IF NOT EXISTS FOR (f:FIR) ON (f.district)",
    "CREATE INDEX station_district IF NOT EXISTS FOR (s:Station) ON (s.district)",
]

# The big batched query — one round-trip per `--batch` records.
# Uses CALL { ... } IN TRANSACTIONS-style structure flattened into a single
# UNWIND so AuraDB Free runs it as a normal write tx.
INGEST_BATCH = """
UNWIND $rows AS row

// --- Station ---
MERGE (s:Station {name: row.station.name})
  ON CREATE SET s.lat = row.station.lat,
                s.lng = row.station.lng,
                s.district = row.station.district,
                s.created_at = datetime()
  ON MATCH  SET s.updated_at = datetime()

// --- FIR ---
MERGE (f:FIR {fir_no: row.fir.fir_no})
  ON CREATE SET f.crime_type = row.fir.crime_type,
                f.date_registered = row.fir.date_registered,
                f.time_registered = row.fir.time_registered,
                f.status = row.fir.status,
                f.ipc_sections = row.fir.ipc_sections,
                f.district = row.fir.district,
                f.modus_operandi = row.fir.modus_operandi,
                f.narrative = row.fir.narrative,
                f.linked_fir_nos = row.fir.linked_fir_nos,
                f.created_at = datetime(),
                f._source_system = 'synthetic_firs_v1'
  ON MATCH  SET f.updated_at = datetime()

MERGE (f)-[:AT_STATION]->(s)

// --- Location (optional) ---
FOREACH (_ IN CASE WHEN row.location IS NULL THEN [] ELSE [1] END |
  MERGE (l:Location {h3_index: row.location.h3_index})
    ON CREATE SET l.h3_resolution = row.location.h3_resolution,
                  l.lat = row.location.lat,
                  l.lng = row.location.lng,
                  l.text = row.location.text,
                  l.created_at = datetime()
  MERGE (f)-[:OCCURRED_AT]->(l)
)

// --- Persons + role-edges ---
WITH f, row
UNWIND row.persons AS person
MERGE (p:Person {id: person.id})
  ON CREATE SET p.name = person.name,
                p.age = person.age,
                p.gender = person.gender,
                p.created_at = datetime()
  ON MATCH  SET p.updated_at = datetime()

// Phone (only on complainants) — never overwrite with null
FOREACH (_ IN CASE WHEN person.phone IS NULL THEN [] ELSE [1] END |
  SET p.phone = person.phone
)

// Role-specific edges — one query per role using FOREACH-as-IF
FOREACH (_ IN CASE WHEN person.role = 'ACCUSED_IN' THEN [1] ELSE [] END |
  MERGE (p)-[r:ACCUSED_IN]->(f)
    ON CREATE SET r.status = person.status,
                  r.created_at = datetime()
)
FOREACH (_ IN CASE WHEN person.role = 'COMPLAINANT_IN' THEN [1] ELSE [] END |
  MERGE (p)-[:COMPLAINANT_IN]->(f)
)
FOREACH (_ IN CASE WHEN person.role = 'VICTIM_IN' THEN [1] ELSE [] END |
  MERGE (p)-[r:VICTIM_IN]->(f)
    ON CREATE SET r.relation = person.relation
)
"""


# --------------------------------------------------------------------------- #
# Driver helpers                                                              #
# --------------------------------------------------------------------------- #

def connect() -> Driver:
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    pw = os.environ.get("NEO4J_PASSWORD")
    if not (uri and user and pw):
        log.error("Missing NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD env vars.")
        log.error("Set them and re-run. See README.md for AuraDB Free setup.")
        sys.exit(2)
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        driver.verify_connectivity()
        log.info("Connected to Neo4j at %s", uri)
        return driver
    except AuthError as e:
        log.error("Auth failed: %s", e)
        sys.exit(2)
    except ServiceUnavailable as e:
        log.error("Neo4j unreachable: %s", e)
        sys.exit(2)


def apply_schema(driver: Driver) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            log.info("Schema: %s", stmt.split(' IF ')[0])
            session.run(stmt)
        for stmt in INDEXES:
            log.info("Index:  %s", stmt.split(' IF ')[0])
            session.run(stmt)
    log.info("Schema + indexes applied.")


def wipe_database(driver: Driver) -> None:
    log.warning("--reset flag set. Deleting ALL nodes + relationships.")
    with driver.session() as session:
        # Delete in chunks to avoid OOM on AuraDB Free
        while True:
            res = session.run(
                "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted"
            ).single()
            deleted = res["deleted"] if res else 0
            if not deleted:
                break
            log.warning("  ...deleted %d nodes", deleted)
    log.warning("Database wiped.")


def ingest(driver: Driver, input_path: Path, limit: int | None, batch_size: int) -> dict:
    log.info("Streaming FIRs from %s (limit=%s, batch=%d)",
             input_path, limit or "ALL", batch_size)

    total_rows = 0
    total_persons = 0
    t0 = time.time()

    payload_stream = (build_payload(rec) for rec in stream_jsonl(input_path, limit))

    with driver.session() as session:
        for batch in tqdm(batched(payload_stream, batch_size),
                          desc="Ingesting FIR batches", unit="batch"):
            session.execute_write(
                lambda tx, rows=batch: tx.run(INGEST_BATCH, rows=rows).consume()
            )
            total_rows += len(batch)
            total_persons += sum(len(r["persons"]) for r in batch)

    elapsed = time.time() - t0
    rate = total_rows / elapsed if elapsed else 0
    log.info("Primary ingest done: %d FIRs, %d person-edges in %.1fs (%.0f FIRs/sec)",
             total_rows, total_persons, elapsed, rate)
    return {"firs": total_rows, "person_edges": total_persons, "elapsed_s": elapsed}


def report_stats(driver: Driver) -> None:
    log.info("Computing final graph statistics...")
    queries = [
        ("Person nodes",       "MATCH (p:Person)   RETURN count(p) AS n"),
        ("FIR nodes",          "MATCH (f:FIR)      RETURN count(f) AS n"),
        ("Station nodes",      "MATCH (s:Station)  RETURN count(s) AS n"),
        ("Location nodes",     "MATCH (l:Location) RETURN count(l) AS n"),
        ("ACCUSED_IN rels",    "MATCH ()-[r:ACCUSED_IN]->()    RETURN count(r) AS n"),
        ("COMPLAINANT_IN rels","MATCH ()-[r:COMPLAINANT_IN]->() RETURN count(r) AS n"),
        ("VICTIM_IN rels",     "MATCH ()-[r:VICTIM_IN]->()     RETURN count(r) AS n"),
        ("AT_STATION rels",    "MATCH ()-[r:AT_STATION]->()    RETURN count(r) AS n"),
        ("OCCURRED_AT rels",   "MATCH ()-[r:OCCURRED_AT]->()   RETURN count(r) AS n"),
        ("CO_ACCUSED_WITH rels","MATCH ()-[r:CO_ACCUSED_WITH]-() RETURN count(r)/2 AS n"),
        ("CO_LOCATED_WITH rels","MATCH ()-[r:CO_LOCATED_WITH]-() RETURN count(r)/2 AS n"),
    ]
    print()
    print("=" * 60)
    print(f"  Graph statistics")
    print("=" * 60)
    with driver.session() as session:
        for label, cypher in queries:
            try:
                n = session.run(cypher).single()["n"]
                print(f"  {label:<25} {n:>12,}")
            except Exception as e:  # noqa: BLE001
                print(f"  {label:<25} (skipped: {e})")
    print("=" * 60)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest synthetic FIRs into Neo4j and build the criminal network graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", required=True, type=Path,
                        help="Path to FIRs JSONL (e.g. ../data/firs.jsonl)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max FIRs to ingest (default: all)")
    parser.add_argument("--batch", type=int, default=500,
                        help="Rows per UNWIND batch (default 500; AuraDB Free sweet-spot)")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe database before ingesting (DESTRUCTIVE).")
    parser.add_argument("--skip-derived", action="store_true",
                        help="Skip the CO_ACCUSED_WITH / CO_LOCATED_WITH derivation pass.")
    parser.add_argument("--skip-centrality", action="store_true",
                        help="Skip the PageRank-style centrality computation.")
    args = parser.parse_args()

    if not args.input.exists():
        log.error("Input file not found: %s", args.input)
        return 1

    driver = connect()
    try:
        if args.reset:
            wipe_database(driver)

        apply_schema(driver)
        ingest(driver, args.input, args.limit, args.batch)

        if not args.skip_derived:
            # Lazy import so the primary path doesn't pay for it if disabled.
            from derived_edges import (
                compute_co_accused,
                compute_co_located,
                compute_centrality,
            )
            log.info("Computing CO_ACCUSED_WITH edges...")
            compute_co_accused(driver)
            log.info("Computing CO_LOCATED_WITH edges...")
            compute_co_located(driver)
            if not args.skip_centrality:
                log.info("Computing centrality (top 100 gang hubs)...")
                top = compute_centrality(driver, top_n=100)
                print()
                print("=" * 60)
                print("  Top 10 Person nodes by centrality (gang-hub candidates)")
                print("=" * 60)
                for i, row in enumerate(top[:10], 1):
                    print(f"  {i:>2}. {row['name']:<25} score={row['score']:.4f}  cases={row['case_count']}")
                print("=" * 60)

        report_stats(driver)
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
