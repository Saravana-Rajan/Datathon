"""Unit tests for the cypher-generator Catalyst Function.

Run from the function dir:

    cd app/backend/functions/cypher-generator
    pytest test_cypher_generator.py -v

The tests are 100% offline — no Neo4j, no QuickML. We inject a fake LLM and
fake executor into `run_cypher_pipeline` and provide tiny stand-ins for
neo4j.graph.Node / Relationship to exercise the React-Flow reshaper.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

# Make this directory importable AND make sure index.py / schema.py / safety.py
# are picked up directly (the function bundle layout flattens them).
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from index import (  # noqa: E402
    _extract_cypher,
    generate_cypher,
    records_to_graph,
    run_cypher_pipeline,
)
from safety import (  # noqa: E402
    cap_depth,
    enforce_limit,
    is_safe_cypher,
)


# ---------------------------------------------------------------------------
# Fake neo4j.graph.Node / Relationship for the reshape tests
# ---------------------------------------------------------------------------

class FakeNode:
    """Mimics enough of neo4j.graph.Node for the reshaper."""

    def __init__(self, element_id: str, labels: list[str], props: dict[str, Any]) -> None:
        self.element_id = element_id
        self.labels = labels
        self._props = props

    # neo4j.graph.Node implements __iter__ over keys and __getitem__ for props.
    def __iter__(self):
        return iter(self._props)

    def __getitem__(self, key: str) -> Any:
        return self._props[key]

    def keys(self):
        return self._props.keys()

    def values(self):
        return self._props.values()


class FakeRel:
    """Mimics enough of neo4j.graph.Relationship for the reshaper."""

    def __init__(
        self,
        element_id: str,
        rel_type: str,
        start: FakeNode,
        end: FakeNode,
        props: dict[str, Any] | None = None,
    ) -> None:
        self.element_id = element_id
        self.type = rel_type
        self.start_node = start
        self.end_node = end
        self._props = props or {}

    def __iter__(self):
        return iter(self._props)

    def __getitem__(self, key: str) -> Any:
        return self._props[key]

    def keys(self):
        return self._props.keys()

    def values(self):
        return self._props.values()


class FakeRecord(dict):
    """A Neo4j Record-ish container."""

    def values(self):
        return list(super().values())


# ---------------------------------------------------------------------------
# Cypher extraction
# ---------------------------------------------------------------------------

def test_extract_cypher_handles_markdown_fence():
    raw = "```cypher\nMATCH (p:Person) RETURN p LIMIT 10\n```"
    assert _extract_cypher(raw) == "MATCH (p:Person) RETURN p LIMIT 10"


def test_extract_cypher_strips_leading_label():
    raw = "CYPHER: MATCH (p:Person) RETURN p LIMIT 10"
    assert _extract_cypher(raw) == "MATCH (p:Person) RETURN p LIMIT 10"


# ---------------------------------------------------------------------------
# Safety: depth cap
# ---------------------------------------------------------------------------

def test_cap_depth_caps_excessive_traversal():
    cy = "MATCH (a:Person)-[*1..10]-(b) RETURN a, b"
    out, warnings = cap_depth(cy, max_depth=3)
    assert "*1..3" in out
    assert "depth_capped_to_3" in warnings


def test_cap_depth_bounds_unbounded_traversal():
    cy = "MATCH (a:Person)-[*]-(b) RETURN a, b"
    out, warnings = cap_depth(cy, max_depth=3)
    assert "*1..3" in out
    assert any("unbounded_traversal_bounded_to_3" == w for w in warnings)


def test_cap_depth_leaves_safe_traversal_untouched():
    cy = "MATCH (a:Person)-[*1..2]-(b) RETURN a, b"
    out, warnings = cap_depth(cy, max_depth=3)
    assert "*1..2" in out
    assert warnings == []


# ---------------------------------------------------------------------------
# Safety: LIMIT injection
# ---------------------------------------------------------------------------

def test_enforce_limit_appends_when_missing():
    cy = "MATCH (p:Person) RETURN p"
    out, warnings = enforce_limit(cy, default_limit=50)
    assert out.endswith("LIMIT 50")
    assert "limit_injected:50" in warnings


def test_enforce_limit_leaves_existing_limit_alone():
    cy = "MATCH (p:Person) RETURN p LIMIT 10"
    out, warnings = enforce_limit(cy, default_limit=50)
    assert out == cy
    assert warnings == []


# ---------------------------------------------------------------------------
# Safety: hard rejects
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "evil",
    [
        "DROP DATABASE neo4j",
        "MATCH (p:Person) DELETE p",
        "CREATE (p:Person {name: 'x'}) RETURN p",
        "MATCH (p) SET p.flag = true RETURN p",
        "MERGE (p:Person {name: 'x'}) RETURN p",
        "MATCH (p) DETACH DELETE p",
        "CALL apoc.cypher.runMany('CREATE (x)', {})",
        "LOAD CSV FROM 'http://evil.com/x.csv' AS row RETURN row",
    ],
)
def test_injection_attempts_are_rejected(evil: str):
    ok, reasons, _ = is_safe_cypher(evil)
    assert ok is False
    assert reasons, "rejection must surface a reason"


def test_comments_are_rejected():
    ok, reasons, _ = is_safe_cypher("MATCH (p:Person) // sneaky\nRETURN p LIMIT 10")
    assert ok is False
    assert any("comments_not_allowed" in r for r in reasons)


def test_unknown_rel_type_rejected():
    ok, reasons, _ = is_safe_cypher("MATCH (a:Person)-[:HACKS]-(b) RETURN a, b LIMIT 5")
    assert ok is False
    assert any("rel_type_not_whitelisted:HACKS" == r for r in reasons)


# ---------------------------------------------------------------------------
# Safety: end-to-end fix-ups on good Cypher
# ---------------------------------------------------------------------------

def test_safe_cypher_with_deep_traversal_is_capped_not_rejected():
    cy = "MATCH (p:Person {name:'Ravi Kumar'})-[*1..10]-(c) RETURN p, c"
    ok, warnings, fixed = is_safe_cypher(cy)
    assert ok is True
    assert "*1..3" in fixed
    assert any("depth_capped_to_3" in w for w in warnings)
    # LIMIT was missing — it should have been injected.
    assert "LIMIT 50" in fixed


def test_safe_cypher_with_limit_passes_through():
    cy = "MATCH (p:Person) RETURN p LIMIT 5"
    ok, warnings, fixed = is_safe_cypher(cy)
    assert ok is True
    assert fixed.strip().endswith("LIMIT 5")


# ---------------------------------------------------------------------------
# Prompt-driven Cypher generation (LLM stubbed)
# ---------------------------------------------------------------------------

def _fake_llm_factory(canned: str):
    """Return an LLM stand-in that ignores the prompt and returns `canned`."""
    def _llm(prompt: str) -> str:
        return canned
    return _llm


def test_network_query_around_a_person():
    llm = _fake_llm_factory(
        "MATCH (p:Person {name:'Ravi Kumar'})-[*1..3]-(c) RETURN p, c LIMIT 50"
    )
    cypher, warnings = generate_cypher(
        "Show network around Ravi Kumar",
        {"entities": {"person": "Ravi Kumar"}},
        llm=llm,
    )
    assert "MATCH (p:Person" in cypher
    assert "Ravi Kumar" in cypher
    assert "*1..3" in cypher
    assert "LIMIT 50" in cypher
    assert warnings == []


def test_gang_hubs_centrality_query():
    llm = _fake_llm_factory(
        "MATCH (p:Person)-[r:CO_ACCUSED_WITH]-() "
        "WHERE p.centrality > 0.05 "
        "RETURN p ORDER BY p.centrality DESC LIMIT 20"
    )
    cypher, _warnings = generate_cypher(
        "Find gang hubs in Whitefield",
        {"entities": {"location": "Whitefield"}},
        llm=llm,
    )
    assert "ORDER BY" in cypher
    assert "centrality" in cypher
    assert "LIMIT 20" in cypher


# ---------------------------------------------------------------------------
# Full pipeline: rejects writes, caps depth, executes happy path
# ---------------------------------------------------------------------------

def test_pipeline_rejects_drop_database():
    llm = _fake_llm_factory("DROP DATABASE neo4j")
    result = run_cypher_pipeline(
        {"request_id": "r1", "query": "DROP DATABASE", "router_decision": {}},
        llm=llm,
        executor=lambda cy: pytest.fail("executor should not run on unsafe cypher"),
    )
    assert result["ok"] is False
    assert any("unsafe_cypher:forbidden_keyword:drop" in w for w in result["warnings"])
    assert result["results"] == {"nodes": [], "edges": []}


def test_pipeline_caps_deep_traversal_and_still_executes():
    llm = _fake_llm_factory(
        "MATCH (p:Person {name:'Ravi Kumar'})-[*1..10]-(c) RETURN p, c"
    )
    seen_cypher: list[str] = []

    def fake_executor(cy: str):
        seen_cypher.append(cy)
        # Return an empty result set — we only care that execution happened
        # on a capped query.
        return []

    result = run_cypher_pipeline(
        {"request_id": "r2", "query": "Network around Ravi Kumar",
         "router_decision": {"entities": {"person": "Ravi Kumar"}}},
        llm=llm,
        executor=fake_executor,
    )
    assert result["ok"] is True
    assert seen_cypher, "executor should have been called"
    assert "*1..3" in seen_cypher[0]
    assert "LIMIT 50" in seen_cypher[0]
    assert any("depth_capped_to_3" in w for w in result["warnings"])


def test_pipeline_reshapes_records_to_react_flow():
    ravi = FakeNode("n1", ["Person"], {"id": "p_ravi", "name": "Ravi Kumar"})
    suresh = FakeNode("n2", ["Person"], {"id": "p_suresh", "name": "Suresh"})
    rel = FakeRel("r1", "CO_ACCUSED_WITH", ravi, suresh, {"weight": 0.8})

    llm = _fake_llm_factory("MATCH (a:Person)-[r:CO_ACCUSED_WITH]-(b:Person) RETURN a, r, b LIMIT 50")
    result = run_cypher_pipeline(
        {"request_id": "r3", "query": "Show co-accused around Ravi",
         "router_decision": {"entities": {"person": "Ravi Kumar"}}},
        llm=llm,
        executor=lambda cy: [FakeRecord(a=ravi, r=rel, b=suresh)],
    )
    assert result["ok"] is True
    nodes = result["results"]["nodes"]
    edges = result["results"]["edges"]
    assert len(nodes) == 2
    assert {n["type"] for n in nodes} == {"Person"}
    # Position is React-Flow-shaped, set to 0/0 (client lays out).
    assert all(n["position"] == {"x": 0, "y": 0} for n in nodes)
    assert len(edges) == 1
    assert edges[0]["type"] == "CO_ACCUSED_WITH"
    assert edges[0]["data"] == {"weight": 0.8}
    # Source / target ids reference real node ids in the node list.
    node_ids = {n["id"] for n in nodes}
    assert edges[0]["source"] in node_ids
    assert edges[0]["target"] in node_ids


# ---------------------------------------------------------------------------
# Pipeline: graceful handling of malformed / empty LLM output
# ---------------------------------------------------------------------------

def test_pipeline_handles_empty_llm_output():
    result = run_cypher_pipeline(
        {"request_id": "r4", "query": "Some query", "router_decision": {}},
        llm=_fake_llm_factory(""),
        executor=lambda cy: pytest.fail("executor should not run"),
    )
    assert result["ok"] is False
    assert any("llm_returned_empty_cypher" in w for w in result["warnings"])


def test_pipeline_handles_empty_query():
    result = run_cypher_pipeline(
        {"request_id": "r5", "query": "", "router_decision": {}},
        llm=_fake_llm_factory("MATCH (p:Person) RETURN p LIMIT 10"),
        executor=lambda cy: pytest.fail("executor should not run"),
    )
    assert result["ok"] is False
    assert "empty_query" in result["warnings"]


# ---------------------------------------------------------------------------
# records_to_graph: de-duplicates repeated nodes across multiple records
# ---------------------------------------------------------------------------

def test_records_to_graph_dedupes_nodes_across_records():
    ravi = FakeNode("n1", ["Person"], {"id": "p_ravi", "name": "Ravi Kumar"})
    suresh = FakeNode("n2", ["Person"], {"id": "p_suresh", "name": "Suresh"})
    rel1 = FakeRel("r1", "CO_ACCUSED_WITH", ravi, suresh, {"weight": 0.8})
    rel2 = FakeRel("r2", "CO_ACCUSED_WITH", ravi, suresh, {"weight": 0.9})

    graph = records_to_graph([
        FakeRecord(a=ravi, r=rel1, b=suresh),
        FakeRecord(a=ravi, r=rel2, b=suresh),
    ])
    # Ravi + Suresh appear twice in records but only once in nodes.
    assert len(graph["nodes"]) == 2
    # Both relationships preserved (different element_ids).
    assert len(graph["edges"]) == 2
