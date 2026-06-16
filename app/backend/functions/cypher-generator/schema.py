"""Neo4j graph schema reference for the cypher-generator function.

Single source of truth for what the criminal-network graph looks like.
We feed `NEO4J_SCHEMA` into the LLM prompt so it can ground its Cypher
output in real labels + relationship types, and the safety / depth-cap
layer reuses `ALLOWED_NODE_LABELS`, `ALLOWED_REL_TYPES`, and `MAX_REL_DEPTH`
to decide whether generated Cypher is acceptable.

Centrality is pre-computed during nightly ingestion (see
`app/data-pipeline/neo4j_ingest.py`) and persisted as a `Person.centrality`
property — the LLM is told to use that property directly instead of calling
GDS procedures, which Catalyst Functions can't invoke from AuraDB Free.
"""

from __future__ import annotations


# Node labels the graph knows about. Anything outside this set is rejected
# by safety.py.
ALLOWED_NODE_LABELS: frozenset[str] = frozenset({
    "Person",
    "FIR",
    "Station",
    "Location",
})

# Relationship types the graph uses. Same idea — anything else fails safety.
ALLOWED_REL_TYPES: frozenset[str] = frozenset({
    "ACCUSED_IN",
    "COMPLAINANT_IN",
    "VICTIM_IN",
    "AT_STATION",
    "OCCURRED_AT",
    "CO_ACCUSED_WITH",
    "CO_LOCATED_WITH",
})

# Hard cap on variable-length path traversals. The LLM is told to stay <= 3,
# safety.py downgrades anything bigger.
MAX_REL_DEPTH: int = 3

# Default LIMIT injected when the LLM forgets one.
DEFAULT_LIMIT: int = 50


NEO4J_SCHEMA: str = """
NODES:
  (:Person {id, name, age, gender, phone, status, centrality})
  (:FIR {fir_no, date, crime_type, station, narrative})
  (:Station {name, district, lat, lng})
  (:Location {h3_index, name})

RELATIONSHIPS:
  (:Person)-[:ACCUSED_IN]->(:FIR)
  (:Person)-[:COMPLAINANT_IN]->(:FIR)
  (:Person)-[:VICTIM_IN]->(:FIR)
  (:FIR)-[:AT_STATION]->(:Station)
  (:FIR)-[:OCCURRED_AT]->(:Location)
  (:Person)-[:CO_ACCUSED_WITH {weight}]-(:Person)
  (:Person)-[:CO_LOCATED_WITH {h3, count}]-(:Person)

COMMON PATTERNS:
  -- N-hop network (cap at *1..3)
  MATCH (start:Person {name: $name})-[*1..3]-(connected) RETURN start, connected LIMIT 50

  -- MO matching (crimes of the same type after a given date)
  MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR {crime_type: $type})
  WHERE f.date > date($since)
  RETURN p, f LIMIT 50

  -- Gang hubs (centrality is pre-computed and stored on Person.centrality)
  MATCH (p:Person)
  WHERE p.centrality > 0.05
  RETURN p
  ORDER BY p.centrality DESC
  LIMIT 20

  -- Stations in a district
  MATCH (s:Station {district: $district})<-[:AT_STATION]-(f:FIR)
  RETURN s, f LIMIT 50

  -- Co-accused cluster around a seed person
  MATCH (p:Person {name: $name})-[r:CO_ACCUSED_WITH]-(other:Person)
  RETURN p, other, r ORDER BY r.weight DESC LIMIT 25
""".strip()


__all__ = [
    "NEO4J_SCHEMA",
    "ALLOWED_NODE_LABELS",
    "ALLOWED_REL_TYPES",
    "MAX_REL_DEPTH",
    "DEFAULT_LIMIT",
]
