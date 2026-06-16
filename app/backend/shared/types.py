"""Shared Pydantic v2 models for KSP Saathi backend.

These models are the contract between the orchestrator (Catalyst Circuits)
and every specialist function: intent-router, sql-generator, cypher-generator,
rag-retriever, synthesizer, audit-logger.

Keep this file dependency-free apart from `pydantic` + stdlib — it is
imported by every function bundle.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Intent enum — mirrors the router's tool taxonomy (design.md §10.2)
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    """Routing categories emitted by the intent-router function."""

    TABULAR_QUERY = "tabular_query"        # Data Store SQL
    GRAPH_QUERY = "graph_query"            # Neo4j Cypher
    GEO_QUERY = "geo_query"                # H3 cluster / hotspot
    PREDICTIVE_QUERY = "predictive_query"  # Zia AutoML forecast
    LOOKUP = "lookup"                      # RAG retrieval over narratives
    META_QUERY = "meta_query"              # "why did you say that" / audit lookup
    MIXED = "mixed"                        # multiple of the above in parallel


# ---------------------------------------------------------------------------
# Language enum — used by routers + synthesizers for prompt selection
# ---------------------------------------------------------------------------

Language = Literal["kn", "en", "hi", "mixed"]


# ---------------------------------------------------------------------------
# Router decision
# ---------------------------------------------------------------------------

class RouterDecision(BaseModel):
    """Output of the intent-router function."""

    model_config = ConfigDict(use_enum_values=True)

    intent: Intent
    language: Language = "en"
    entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted slots: station, district, date_range, accused_name, ipc_section, etc.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        default="",
        description="One-paragraph human-readable trace for the audit drawer.",
    )
    sub_intents: list[Intent] = Field(
        default_factory=list,
        description="When intent == MIXED, the list of specialist tools to fan out.",
    )


# ---------------------------------------------------------------------------
# Tool result — every specialist function returns one of these
# ---------------------------------------------------------------------------

class ToolResult(BaseModel):
    """Uniform envelope for every specialist tool's output."""

    tool_name: str = Field(
        description="One of: sql_generator, cypher_generator, rag_retriever, "
                    "geo_hotspot, zia_forecast, audit_lookup."
    )
    success: bool
    data: Any = Field(
        default=None,
        description="Rows / nodes / chunks / forecast — shape depends on tool.",
    )
    error: str | None = Field(
        default=None,
        description="Human-readable failure message, populated only when success=False.",
    )
    latency_ms: int | None = Field(
        default=None,
        description="Wall-clock latency for the specialist call.",
    )
    raw_query: str | None = Field(
        default=None,
        description="The generated SQL / Cypher / search string — kept for the audit trail.",
    )
    source_count: int | None = Field(
        default=None,
        description="Number of underlying records the result is grounded in.",
    )


# ---------------------------------------------------------------------------
# Synthesizer I/O
# ---------------------------------------------------------------------------

class SynthesizerInput(BaseModel):
    """Bundle handed to the synthesizer (Gemini 2.5 Pro or Qwen 2.5 14B)."""

    query: str
    lang: Language = "en"
    tool_results: list[ToolResult] = Field(default_factory=list)
    role: str | None = Field(
        default=None,
        description="RBAC role of the asking officer — affects PII masking.",
    )
    session_context: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent turns from the same session for context-aware replies.",
    )


class VizSpec(BaseModel):
    """Optional visualization payload the frontend renders alongside the answer."""

    kind: Literal["none", "map", "graph", "chart", "table"] = "none"
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditStep(BaseModel):
    """One entry in the audit chain — surfaced in the 'Why?' drawer."""

    step: str = Field(description="Stage name, e.g. 'router', 'sql_generator', 'synthesizer'.")
    detail: str = Field(description="Short human-readable description.")
    payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None


class SynthesizerOutput(BaseModel):
    """What the synthesizer returns to the orchestrator."""

    answer_text: str
    viz_spec: VizSpec = Field(default_factory=VizSpec)
    audit_chain: list[AuditStep] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Cited records (FIR nos, narrative chunk IDs, graph nodes).",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    language: Language = "en"
