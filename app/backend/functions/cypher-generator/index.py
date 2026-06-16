"""KSP Saathi — Cypher Generator Catalyst Function.

Advanced I/O endpoint. Given a natural-language criminal-network question
and the upstream router decision (entities: person / location / time),
this function:

    1. Builds a Cypher-generation prompt for Qwen 2.5 14B Instruct on
       Catalyst QuickML LLM Serving.
    2. Calls the model and extracts the raw Cypher.
    3. Runs `safety.is_safe_cypher` — rejects writes, caps `*1..N` depth at
       3 hops, and injects `LIMIT 50` if the model forgot one.
    4. Executes the validated Cypher against Neo4j AuraDB via the shared
       neo4j_client driver.
    5. Re-shapes the Neo4j Records into the `{nodes, edges}` format the
       React-Flow `NetworkGraph.tsx` component expects.
    6. Returns `{cypher, results, execution_ms, warnings}`.

This function never throws to Catalyst — every error path returns a JSON
body with `ok: False` so Circuits can decide to retry or fall back to RAG.

See design.md §5.5 (criminal network visualisation), §6.1 (architecture),
§11.3 (audit log requirements).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import traceback
from typing import Any

# Make `shared/` importable when this function is bundled solo.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from schema import (  # noqa: E402  (sys.path mutation above)
    NEO4J_SCHEMA,
    DEFAULT_LIMIT,
    MAX_REL_DEPTH,
)
from safety import is_safe_cypher  # noqa: E402

logger = logging.getLogger("ksp_saathi.cypher_generator")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Tunables — env-overridable so we don't redeploy for prompt / model tweaks
# ---------------------------------------------------------------------------

QUICKML_LLM_ENDPOINT = os.getenv("QUICKML_LLM_ENDPOINT", "")
QUICKML_ENDPOINT_KEY = os.getenv("QUICKML_ENDPOINT_KEY", "")
QUICKML_OAUTH_TOKEN = os.getenv("QUICKML_OAUTH_TOKEN", "")
QUICKML_ORG_ID = os.getenv("CATALYST_ORG_ID", "")
QUICKML_ENVIRONMENT = os.getenv("CATALYST_ENVIRONMENT", "Development")
QUICKML_MODEL_NAME = os.getenv("QUICKML_MODEL", "qwen-2.5-14b-instruct")

MAX_NODES_RETURNED = int(os.getenv("CYPHER_GEN_MAX_NODES", "200"))


# ---------------------------------------------------------------------------
# Prompt building — prefer shared/prompts.py, fall back to local builder
# ---------------------------------------------------------------------------

def _local_cypher_gen_prompt(
    query: str,
    entities: dict[str, Any] | None,
    schema: str,
) -> str:
    """Mirror of shared.prompts.cypher_gen_prompt used if shared isn't deployed."""
    entities = entities or {}
    entity_block = json.dumps(entities, ensure_ascii=False, indent=2)
    return f"""You are a Cypher generator for the Karnataka State Police criminal-network graph (Neo4j AuraDB).

HARD RULES:
- Output ONE read-only Cypher statement.
- Allowed clauses: MATCH, OPTIONAL MATCH, RETURN, WITH, WHERE, ORDER BY, LIMIT, UNWIND, DISTINCT.
- FORBIDDEN: CREATE, DELETE, DETACH, SET, MERGE, REMOVE, DROP, CALL, LOAD CSV, FOREACH.
- Variable-length traversals must be bounded and <= {MAX_REL_DEPTH} hops (`*1..3`).
- Always include LIMIT; default LIMIT {DEFAULT_LIMIT}.
- Return enough properties for a React-Flow renderer (id/fir_no, name, crime_type).
- Use `p.centrality` for hub queries — never gds.* procedures.
- Return ONLY the Cypher, no prose, no markdown fences.

NEO4J SCHEMA:
{schema}

ROUTER ENTITIES:
{entity_block}

USER QUERY:
{query.strip()}

CYPHER:"""


def _build_prompt(query: str, entities: dict[str, Any] | None) -> str:
    try:
        from shared.prompts import cypher_gen_prompt  # type: ignore
        return cypher_gen_prompt(query, entities, NEO4J_SCHEMA)
    except Exception:  # noqa: BLE001 — fallback is intentional
        return _local_cypher_gen_prompt(query, entities, NEO4J_SCHEMA)


# ---------------------------------------------------------------------------
# QuickML LLM call (Qwen 2.5 14B Instruct on Catalyst)
# ---------------------------------------------------------------------------

def _call_qwen(prompt: str, *, temperature: float = 0.1, max_tokens: int = 512) -> str:
    """Call the QuickML LLM Serving endpoint and return the model's text."""
    if not (QUICKML_LLM_ENDPOINT and QUICKML_ENDPOINT_KEY and QUICKML_OAUTH_TOKEN):
        raise RuntimeError(
            "quickml_not_configured: QUICKML_LLM_ENDPOINT/KEY/OAUTH_TOKEN must be set."
        )

    import httpx  # local import keeps cold-start cheap

    headers = {
        "Authorization": f"Zoho-oauthtoken {QUICKML_OAUTH_TOKEN}",
        "X-QUICKML-ENDPOINT-KEY": QUICKML_ENDPOINT_KEY,
        "CATALYST-ORG": QUICKML_ORG_ID,
        "Environment": QUICKML_ENVIRONMENT,
        "Content-Type": "application/json",
    }
    body = {
        "prompt": prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "instructions": "Output only valid Cypher. No prose. No markdown.",
    }

    with httpx.Client(timeout=18.0) as client:
        resp = client.post(QUICKML_LLM_ENDPOINT, headers=headers, json=body)
        resp.raise_for_status()
        payload = resp.json()

    # QuickML response shape varies; accept the common variants.
    if isinstance(payload, dict):
        for key in ("output", "text", "response", "completion"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("output", "text", "response", "completion"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val
    raise RuntimeError(
        "quickml_unexpected_response_shape: "
        f"keys={list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
    )


# ---------------------------------------------------------------------------
# Cypher extraction
# ---------------------------------------------------------------------------

_CYPHER_FENCE_RE = re.compile(r"```(?:cypher)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _extract_cypher(raw_model_output: str) -> str:
    """Pull the Cypher string out of a model response.

    Models sometimes wrap output in ```cypher ... ``` fences or add a leading
    "CYPHER:" label. Strip those.
    """
    if not raw_model_output:
        return ""
    text = raw_model_output.strip()

    m = _CYPHER_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    text = re.sub(r"^\s*CYPHER\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


# ---------------------------------------------------------------------------
# Neo4j → React-Flow result reshaping
# ---------------------------------------------------------------------------

# Catalyst frontend NetworkGraph.tsx expects:
#   nodes: [{ id, type: "Person|FIR|Station|Location", data: {...props},
#             position: {x:0, y:0} }]
#   edges: [{ id, source, target, type: "ACCUSED_IN|CO_ACCUSED_WITH|...",
#             data: {...rel_props} }]
# Positions are 0/0 here — React-Flow's layout engine (dagre / elk) assigns
# them client-side.

_NODE_LABEL_PRIORITY = ("Person", "FIR", "Station", "Location")


def _node_type_from_labels(labels: Any) -> str:
    """Pick the most specific allowed label for a Neo4j node."""
    if not labels:
        return "Unknown"
    label_list = list(labels) if not isinstance(labels, list) else labels
    for preferred in _NODE_LABEL_PRIORITY:
        if preferred in label_list:
            return preferred
    return str(label_list[0]) if label_list else "Unknown"


def _node_identity(node: Any) -> str:
    """Get a stable string id for a Neo4j node.

    Prefer business keys (`id`, `fir_no`, `name`) before falling back to the
    driver's internal element id. React-Flow needs stable string ids across
    duplicate occurrences of the same node in a result set.
    """
    # neo4j.graph.Node: supports indexing into properties + .element_id
    try:
        props = dict(node)
    except Exception:  # noqa: BLE001
        props = {}

    for key in ("id", "fir_no", "name", "h3_index"):
        val = props.get(key)
        if val is not None:
            return f"{_node_type_from_labels(getattr(node, 'labels', None))}::{val}"

    eid = getattr(node, "element_id", None) or getattr(node, "id", None)
    return f"node::{eid}"


def _format_node(node: Any) -> dict[str, Any] | None:
    """Convert a neo4j.graph.Node into a React-Flow node dict."""
    labels = getattr(node, "labels", None)
    if labels is None:
        return None
    try:
        props = dict(node)
    except Exception:  # noqa: BLE001
        props = {}
    return {
        "id": _node_identity(node),
        "type": _node_type_from_labels(labels),
        "data": props,
        "position": {"x": 0, "y": 0},
    }


def _format_edge(rel: Any) -> dict[str, Any] | None:
    """Convert a neo4j.graph.Relationship into a React-Flow edge dict."""
    start_node = getattr(rel, "start_node", None) or getattr(rel, "nodes", [None, None])[0]
    end_node = getattr(rel, "end_node", None) or getattr(rel, "nodes", [None, None])[1]
    if start_node is None or end_node is None:
        return None

    rel_type = getattr(rel, "type", None) or "RELATED"
    try:
        props = dict(rel)
    except Exception:  # noqa: BLE001
        props = {}

    source_id = _node_identity(start_node)
    target_id = _node_identity(end_node)
    edge_eid = getattr(rel, "element_id", None) or getattr(rel, "id", "") or f"{source_id}->{target_id}:{rel_type}"

    return {
        "id": f"e::{edge_eid}",
        "source": source_id,
        "target": target_id,
        "type": str(rel_type),
        "data": props,
    }


def _is_neo4j_node(obj: Any) -> bool:
    return hasattr(obj, "labels") and hasattr(obj, "element_id") or hasattr(obj, "id") and hasattr(obj, "labels")


def _is_neo4j_relationship(obj: Any) -> bool:
    return hasattr(obj, "type") and (hasattr(obj, "start_node") or hasattr(obj, "nodes"))


def _is_neo4j_path(obj: Any) -> bool:
    return hasattr(obj, "nodes") and hasattr(obj, "relationships") and not hasattr(obj, "type")


def records_to_graph(records: Any) -> dict[str, list[dict[str, Any]]]:
    """Walk a Neo4j Result / list of Records and emit `{nodes, edges}`.

    De-duplicates by node identity so the same Person appearing in many
    paths only shows up once in the React-Flow node list.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def _visit(value: Any) -> None:
        if value is None:
            return
        if _is_neo4j_path(value):
            for n in getattr(value, "nodes", []) or []:
                _visit(n)
            for r in getattr(value, "relationships", []) or []:
                _visit(r)
            return
        if _is_neo4j_relationship(value):
            edge = _format_edge(value)
            if edge:
                edges[edge["id"]] = edge
            # Make sure the endpoints land in the node list too.
            for endpoint in (getattr(value, "start_node", None), getattr(value, "end_node", None)):
                if endpoint is not None:
                    _visit(endpoint)
            return
        if _is_neo4j_node(value):
            n = _format_node(value)
            if n:
                nodes[n["id"]] = n
            return
        if isinstance(value, (list, tuple, set)):
            for v in value:
                _visit(v)
            return
        if isinstance(value, dict):
            for v in value.values():
                _visit(v)
            return
        # Scalar — ignore.

    # `records` may be a list of dicts (after `.data()`), a list of Record
    # objects, or an iterable returned by `session.run(...)`.
    try:
        iterable = list(records)
    except TypeError:
        iterable = [records]

    for rec in iterable:
        if hasattr(rec, "values"):
            try:
                for v in rec.values():
                    _visit(v)
                continue
            except Exception:  # noqa: BLE001
                pass
        if isinstance(rec, dict):
            for v in rec.values():
                _visit(v)
        else:
            _visit(rec)

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


# ---------------------------------------------------------------------------
# Neo4j execution
# ---------------------------------------------------------------------------

def _execute_cypher(cypher: str) -> Any:
    """Run `cypher` against Neo4j AuraDB and return the raw Record list.

    We deliberately collect the Records before the session closes so the
    graph reshaper can introspect node/rel objects (Records are only valid
    while their session is alive).
    """
    from shared.neo4j_client import get_session  # type: ignore

    with get_session() as session:
        result = session.run(cypher)
        return list(result)  # eagerly consume — keep Nodes alive after close


# ---------------------------------------------------------------------------
# Catalyst Advanced I/O request/response plumbing
# ---------------------------------------------------------------------------

def _parse_request_body(request: Any) -> dict[str, Any]:
    """Extract the JSON body from a Catalyst Advanced I/O request."""
    if request is None:
        return {}
    for attr in ("body", "data"):
        val = getattr(request, attr, None)
        if isinstance(val, dict):
            return val
        if isinstance(val, (bytes, str)):
            try:
                return json.loads(val if isinstance(val, str) else val.decode())
            except Exception:  # noqa: BLE001
                pass
    if hasattr(request, "get_json"):
        try:
            data = request.get_json()
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            pass
    return {}


def _write_response(response: Any, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body, ensure_ascii=False)
    if hasattr(response, "set_status"):
        try:
            response.set_status(status)
        except Exception:  # noqa: BLE001
            pass
    if hasattr(response, "set_content_type"):
        try:
            response.set_content_type("application/json; charset=utf-8")
        except Exception:  # noqa: BLE001
            pass
    if hasattr(response, "send"):
        response.send(payload)
        return
    if hasattr(response, "write"):
        response.write(payload)
        if hasattr(response, "end"):
            response.end()
        return
    try:
        response.status = status
        response.body = payload
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Core orchestration — exposed for unit tests
# ---------------------------------------------------------------------------

def generate_cypher(
    query: str,
    router_decision: dict[str, Any] | None,
    *,
    llm: Any = None,
) -> tuple[str, list[str]]:
    """Build prompt, call LLM, extract Cypher. Returns `(cypher, warnings)`.

    `llm` is an optional callable `(prompt: str) -> str` for testing.
    """
    warnings: list[str] = []
    router = router_decision or {}
    entities = dict(router.get("entities") or {})
    # Pull common fields onto entities so the prompt sees them.
    for k in ("person", "location", "time"):
        v = router.get(k)
        if v is not None and k not in entities:
            entities[k] = v

    prompt = _build_prompt(query, entities)
    raw = (llm or _call_qwen)(prompt)
    cypher = _extract_cypher(raw)
    if not cypher:
        warnings.append("llm_returned_empty_cypher")
    return cypher, warnings


def run_cypher_pipeline(
    payload: dict[str, Any],
    *,
    llm: Any = None,
    executor: Any = None,
) -> dict[str, Any]:
    """End-to-end pipeline: prompt → LLM → safety → execute → reshape.

    `executor` lets tests pass a fake driver — callable `(cypher) -> records`.
    """
    t0 = time.perf_counter()
    warnings: list[str] = []

    query = (payload.get("query") or "").strip()
    request_id = payload.get("request_id") or ""
    router = payload.get("router_decision") or {}

    if not query:
        return {
            "cypher": "",
            "results": {"nodes": [], "edges": []},
            "execution_ms": 0,
            "warnings": ["empty_query"],
            "ok": False,
            "request_id": request_id,
        }

    # 1. Generate Cypher.
    try:
        cypher, gen_warnings = generate_cypher(query, router, llm=llm)
    except Exception as exc:  # noqa: BLE001
        return {
            "cypher": "",
            "results": {"nodes": [], "edges": []},
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": [f"llm_call_failed:{type(exc).__name__}"],
            "ok": False,
            "request_id": request_id,
        }
    warnings.extend(gen_warnings)

    if not cypher:
        return {
            "cypher": "",
            "results": {"nodes": [], "edges": []},
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": warnings,
            "ok": False,
            "request_id": request_id,
        }

    # 2. Safety validation + auto-fix (depth cap, LIMIT injection).
    ok, reasons, fixed_cypher = is_safe_cypher(cypher)
    if not ok:
        return {
            "cypher": cypher,
            "results": {"nodes": [], "edges": []},
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": warnings + [f"unsafe_cypher:{r}" for r in reasons],
            "ok": False,
            "request_id": request_id,
        }
    # `reasons` here is a list of soft warnings (depth_capped_to_3,
    # limit_injected:50) — surface them.
    warnings.extend(reasons)
    cypher = fixed_cypher

    # 3. Execute.
    try:
        if executor is not None:
            records = executor(cypher)
        else:
            records = _execute_cypher(cypher)
    except Exception as exc:  # noqa: BLE001
        return {
            "cypher": cypher,
            "results": {"nodes": [], "edges": []},
            "execution_ms": int((time.perf_counter() - t0) * 1000),
            "warnings": warnings + [f"execute_failed:{type(exc).__name__}:{exc}"],
            "ok": False,
            "request_id": request_id,
        }

    # 4. Reshape for React-Flow.
    graph = records_to_graph(records)

    # 5. Cap node count (defence-in-depth — LIMIT is already in the Cypher).
    if len(graph["nodes"]) > MAX_NODES_RETURNED:
        warnings.append(f"node_cap_applied:{MAX_NODES_RETURNED}")
        kept_ids = {n["id"] for n in graph["nodes"][:MAX_NODES_RETURNED]}
        graph["nodes"] = graph["nodes"][:MAX_NODES_RETURNED]
        graph["edges"] = [
            e for e in graph["edges"]
            if e["source"] in kept_ids and e["target"] in kept_ids
        ]

    return {
        "cypher": cypher,
        "results": graph,
        "execution_ms": int((time.perf_counter() - t0) * 1000),
        "warnings": warnings,
        "ok": True,
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Catalyst entry point
# ---------------------------------------------------------------------------

def handler(context: Any, basic_io: Any = None) -> Any:
    """Catalyst Advanced I/O entry point. POST only."""
    if basic_io is None and hasattr(context, "get_request_method"):
        request, response = context, None  # type: ignore[assignment]
    elif basic_io is not None and (hasattr(basic_io, "req") or hasattr(basic_io, "request")):
        request = getattr(basic_io, "req", None) or getattr(basic_io, "request", None)
        response = getattr(basic_io, "res", None) or getattr(basic_io, "response", None)
    else:
        request, response = context, basic_io

    try:
        method = (
            (getattr(request, "method", None)
             or getattr(request, "get_request_method", lambda: "POST")()).upper()
            if request else "POST"
        )
        if method not in ("POST", "PUT"):
            _write_response(response, 405, {"ok": False, "error": "method_not_allowed", "allow": "POST"})
            return {"ok": False, "error": "method_not_allowed"}

        body = _parse_request_body(request)
        result = run_cypher_pipeline(body)
        status = 200 if result.get("ok") else 400
        logger.info(
            "cypher-gen request_id=%s ok=%s nodes=%s edges=%s ms=%s warnings=%s",
            result.get("request_id"),
            result.get("ok"),
            len(result.get("results", {}).get("nodes", [])),
            len(result.get("results", {}).get("edges", [])),
            result.get("execution_ms"),
            result.get("warnings"),
        )
        _write_response(response, status, result)
        return result

    except Exception as exc:  # noqa: BLE001 — top-level safety net
        err = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
        }
        logger.exception("cypher-generator failed")
        _write_response(response, 500, err)
        return err
