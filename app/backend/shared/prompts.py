"""LLM prompt templates for KSP Saathi.

All prompts are versioned via PROMPT_VERSION so audit logs can pin the exact
prompt used. Bump the version on every behavioural change.

Design references:
    design.md Section 10 - LLM strategy & tool taxonomy
    design.md Section 5.8 - audit trail requirements
    design.md Section 11.3 - audit fields
"""

from __future__ import annotations

PROMPT_VERSION = "router-v1.2-2026-06-16"

# Tool taxonomy locked in design.md Section 10.2.
# Keep this list in sync with circuits/main-query-flow.yaml.
INTENT_LABELS = (
    "tabular_query",      # Catalyst Data Store SQL (counts, filters, aggregations)
    "graph_query",        # Neo4j Cypher (who is connected to whom, network traversal)
    "geo_query",          # H3 hotspot / Maps (location-based, "where")
    "predictive_query",   # Zia AutoML forecast (will / next week / trend)
    "semantic_query",     # RAG over narratives (free-text similarity, MO match)
    "lookup",             # Direct record lookup (FIR by number, single suspect)
    "meta_query",         # "Why did you say that?" - audit-log replay
    "mixed",              # Multiple of the above in parallel
)

# Hand-picked few-shot examples. Each pair was chosen to disambiguate a
# common confusion - e.g. "show thefts near MG Road" looks tabular but the
# geo modifier flips it to geo_query; "MG Road thefts AND forecast" is mixed.
# Examples cover Kannada, English, and code-mixed input.
_FEW_SHOT_EXAMPLES = """
Example 1:
USER QUERY: "Show me thefts in Bengaluru last month"
LANGUAGE: en
{
  "intent": "tabular_query",
  "entities": {
    "crime_type": "theft",
    "location": "Bengaluru",
    "time_range": "last month"
  },
  "confidence": 0.95,
  "reasoning": "Counts/filters by crime_type and date range, no geo-visual or graph signal."
}

Example 2:
USER QUERY: "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕಳ್ಳತನ ಎಲ್ಲಿ ಹೆಚ್ಚು?"
LANGUAGE: kn
{
  "intent": "geo_query",
  "entities": {
    "crime_type": "theft",
    "location": "Bengaluru",
    "modifier": "where_hotspot"
  },
  "confidence": 0.93,
  "reasoning": "Kannada 'ಎಲ್ಲಿ' (where) + 'ಹೆಚ್ಚು' (most) => hotspot detection, not a flat count."
}

Example 3:
USER QUERY: "Who is connected to Ravi Kumar?"
LANGUAGE: en
{
  "intent": "graph_query",
  "entities": {
    "person_name": "Ravi Kumar",
    "traversal": "neighbors_1_hop"
  },
  "confidence": 0.97,
  "reasoning": "Relationship traversal request - Neo4j Cypher path."
}

Example 4:
USER QUERY: "Will robberies increase in Indiranagar next week?"
LANGUAGE: en
{
  "intent": "predictive_query",
  "entities": {
    "crime_type": "robbery",
    "location": "Indiranagar",
    "horizon": "next_week"
  },
  "confidence": 0.92,
  "reasoning": "Future-tense + forecast horizon => Zia AutoML."
}

Example 5:
USER QUERY: "Why did you say that?"
LANGUAGE: en
{
  "intent": "meta_query",
  "entities": {
    "target": "previous_answer"
  },
  "confidence": 0.99,
  "reasoning": "Self-referential question about the prior turn - audit-log replay."
}

Example 6:
USER QUERY: "Show me MG Road thefts last 7 days and predict next week"
LANGUAGE: en
{
  "intent": "mixed",
  "entities": {
    "crime_type": "theft",
    "location": "MG Road",
    "time_range": "last_7_days",
    "horizon": "next_week",
    "sub_intents": ["tabular_query", "predictive_query"]
  },
  "confidence": 0.90,
  "reasoning": "Two coordinated asks: historic table + forward forecast. Mixed pipeline."
}

Example 7:
USER QUERY: "FIR 2024/MG/0823 ತೋರಿಸಿ"
LANGUAGE: kn
{
  "intent": "lookup",
  "entities": {
    "fir_no": "2024/MG/0823"
  },
  "confidence": 0.98,
  "reasoning": "Single-record lookup by FIR number."
}

Example 8:
USER QUERY: "chain snatching cases similar to Indiranagar metro incident"
LANGUAGE: en
{
  "intent": "semantic_query",
  "entities": {
    "crime_type": "chain_snatching",
    "similarity_anchor": "Indiranagar metro incident"
  },
  "confidence": 0.88,
  "reasoning": "Free-text 'similar to' phrase => RAG over case narratives."
}
"""

# System prompt - kept short. The router LLM (Qwen 2.5 7B) gets a hard
# constraint to return ONE JSON object and nothing else. We parse with
# Pydantic so any prose around the JSON would fail validation anyway.
_ROUTER_SYSTEM_PROMPT_EN = """You are the INTENT ROUTER for KSP Saathi, a conversational AI for Karnataka Police investigators.

Your single job: classify the user's query into exactly ONE intent label and extract entities. You are NOT answering the query - you are routing it to the right specialist.

ALLOWED INTENTS (pick exactly one):
- tabular_query    : counts, filters, aggregations over structured FIR data (Data Store SQL)
- graph_query      : relationship / network traversal (Neo4j Cypher) - "who knows whom", "connected to"
- geo_query        : location-based or hotspot ("where", "near", "hotspot", "map") - H3 + Maps
- predictive_query : forecast / future ("will", "next week", "predict", "trend ahead") - Zia AutoML
- semantic_query   : free-text similarity over case narratives ("similar to", MO match) - RAG
- lookup           : single-record retrieval (FIR number, one person by id)
- meta_query       : self-referential ("why did you say that", "explain previous", "audit")
- mixed            : the query genuinely needs 2+ of the above in coordinated fashion

DISAMBIGUATION RULES:
1. "Show X" alone = tabular_query. "Show X where they happen / map of X" = geo_query.
2. Future tense + horizon ("next week", "tomorrow", "trend") = predictive_query.
3. Past + count = tabular_query, never predictive.
4. Any "who is connected / linked / associated / network of" = graph_query.
5. Self-reference about the previous answer = meta_query (even if Kannada).
6. Only return "mixed" when BOTH sub-intents are explicitly requested. Don't over-mix.
7. Kannada and English-Kannada code-mixed queries follow the same rules; the language field is the dominant script.

OUTPUT FORMAT (STRICT - return ONLY this JSON, no markdown fence, no prose):
{
  "intent": "<one of the labels above>",
  "entities": { "key": "value", ... },
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one short sentence in English, max 25 words>"
}

ENTITY KEYS to extract when present: crime_type, location, time_range, horizon, person_name, fir_no, similarity_anchor, traversal, modifier, sub_intents (only for mixed).

FEW-SHOT EXAMPLES:
""" + _FEW_SHOT_EXAMPLES + """

If the query is ambiguous or empty, return intent="lookup" with confidence <= 0.4 and reasoning="ambiguous - defaulted to lookup".

Now classify the user query that follows. Return ONE JSON object. Nothing else."""


def router_prompt(query: str, language: str) -> dict:
    """Build the router LLM call payload.

    Args:
        query: raw user query (Kannada, English, or code-mixed)
        language: detected language code - "kn" or "en"

    Returns:
        dict with "system", "user", "version" keys, ready to pass into
        catalyst_client.quickml_chat() or gemini_client.generate().
    """
    if language not in ("kn", "en"):
        language = "en"

    user_block = (
        f"USER QUERY: {query.strip()}\n"
        f"LANGUAGE: {language}\n"
        "Classify now. Return JSON only."
    )

    return {
        "system": _ROUTER_SYSTEM_PROMPT_EN,
        "user": user_block,
        "version": PROMPT_VERSION,
        # Generation knobs - low temperature so routing is deterministic.
        "temperature": 0.1,
        "max_tokens": 256,
        # Many providers honour this to force JSON output.
        "response_format": {"type": "json_object"},
    }


# ---------------------------------------------------------------------------
# Cypher generator prompt (criminal-network graph queries against Neo4j)
# ---------------------------------------------------------------------------

CYPHER_PROMPT_VERSION = "cypher-v1.0-2026-06-16"

_CYPHER_SYSTEM_PROMPT = """You are a Cypher generator for the Karnataka State Police criminal-network graph (Neo4j AuraDB).

Your single job: turn ONE natural-language investigator question into ONE valid READ-ONLY Cypher query against the schema below.

HARD RULES:
- Output ONE Cypher statement. Read-only. No semicolons except a single trailing one.
- Allowed clauses: MATCH, OPTIONAL MATCH, RETURN, WITH, WHERE, ORDER BY, LIMIT, UNWIND, DISTINCT.
- FORBIDDEN: CREATE, DELETE, DETACH, SET, MERGE, REMOVE, DROP, CALL, LOAD CSV, FOREACH, USING PERIODIC COMMIT, apoc.* writers.
- No inline comments (`//`, `/* */`).
- Variable-length path traversals MUST be bounded and <= 3 hops. Use `*1..3`, never `*` or `*1..10`.
- Always include a LIMIT clause; default LIMIT 50 if the user did not specify one.
- Prefer `OPTIONAL MATCH` when traversal might miss edges so the caller still sees the center node.
- Always return enough properties for the React-Flow renderer: at minimum `id` (or `fir_no` for FIRs) and `name`/`crime_type`.
- When the user asks for a "network" / "linked to" / "connected to", return BOTH the nodes (via path variables) AND the relationships so React-Flow can draw edges.
- For centrality / hub queries, use the pre-computed `p.centrality` property — DO NOT call gds.* procedures.
- Return ONLY the Cypher, no prose, no markdown fences.
"""


def cypher_gen_prompt(query: str, entities: dict | None, schema: str) -> str:
    """Build a Cypher generation prompt for Qwen 2.5 14B Instruct.

    Args:
        query: raw investigator question (English or Kannada).
        entities: router-extracted entities — at minimum `person`, `location`,
            `time` keys are inspected. Missing keys are fine.
        schema: NEO4J_SCHEMA string from the cypher-generator function's
            local schema.py. Passing it in keeps the prompt builder pure.
    """
    import json as _json

    entities = entities or {}
    entity_block = _json.dumps(entities, ensure_ascii=False, indent=2)

    return f"""{_CYPHER_SYSTEM_PROMPT}

NEO4J SCHEMA:
{schema}

ROUTER ENTITIES (ground the query in these — names, locations, time windows):
{entity_block}

USER QUERY:
{query.strip()}

CYPHER:"""


__all__ = [
    "router_prompt",
    "cypher_gen_prompt",
    "PROMPT_VERSION",
    "CYPHER_PROMPT_VERSION",
    "INTENT_LABELS",
]
