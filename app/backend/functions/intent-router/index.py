"""KSP Saathi — Intent Router (Catalyst Advanced I/O Function).

Single responsibility: classify each incoming user query into one routing
intent so the orchestrator (Catalyst Circuits) can fan out to the right
specialist (SQL, Cypher, RAG, Hotspot, Forecast, audit-lookup, or mixed).

Contract (POST /):
    REQUEST:  { "query": str, "language_hint": "kn"|"en"|"auto",
                "session_id": str, "user_role": str }
    RESPONSE: { "intent": str, "language": "kn"|"en",
                "entities": dict, "confidence": float,
                "reasoning": str, "router_latency_ms": int,
                "request_id": str }

Pipeline (~300 ms target):
    1. Validate input (Pydantic v2)
    2. Generate request_id (uuid4) for end-to-end tracing
    3. Detect language if hint=auto (Kannada script check ಀ-೿)
    4. Call Catalyst QuickML (Qwen 2.5 7B Instruct) with router prompt
    5. Parse + validate LLM JSON (Pydantic)
    6. Coerce semantic_query -> lookup (spec restricts the output set)
    7. Write audit-log row (best-effort, never fatal)
    8. Return decision JSON

Fallback ladder (if QuickML fails):
    QuickML -> Gemini 2.5 Pro -> deterministic heuristic (last-ditch)

Design references:
    design.md Section 5  (the 9 features)
    design.md Section 6  (architecture)
    design.md Section 10 (LLM strategy & tool taxonomy)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, ValidationError, field_validator

# Make the shared package importable when this function is bundled.
# Catalyst Functions package each function directory standalone, so we
# add the repo's app/backend root to sys.path. In production, `shared/`
# is vendored next to index.py by the deploy pipeline.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent.parent, _HERE):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from shared import catalyst_client, prompts  # noqa: E402

# Gemini fallback is imported lazily — we don't want a missing google-genai
# SDK to break QuickML happy path.
try:
    from shared import gemini_client  # noqa: E402
    _GEMINI_FALLBACK = True
except Exception:  # noqa: BLE001 — best-effort optional import
    gemini_client = None  # type: ignore[assignment]
    _GEMINI_FALLBACK = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ksp_saathi.intent_router")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The set of intent labels this function is allowed to return — locked to
# the contract in the caller spec. Note that `semantic_query` from the
# prompt taxonomy is collapsed to `lookup` (RAG is a flavour of lookup).
ALLOWED_INTENTS = {
    "tabular_query",
    "graph_query",
    "geo_query",
    "predictive_query",
    "lookup",
    "meta_query",
    "mixed",
}

# Kannada Unicode block: U+0C80..U+0CFF.
_KANNADA_RE = re.compile(r"[ಀ-೿]")

# Confidence threshold below which we override to a safe default. Routing
# downstream specialists on a 0.1-confidence guess wastes Circuit time;
# better to return `lookup` and let the synthesizer ask a clarifier.
_MIN_CONFIDENCE = float(os.getenv("ROUTER_MIN_CONFIDENCE", "0.35"))

# Hard cap on latency budget — design.md §9.1 gives the router 300 ms.
_ROUTER_TIMEOUT_S = float(os.getenv("ROUTER_TIMEOUT_S", "8.0"))


# ---------------------------------------------------------------------------
# I/O models
# ---------------------------------------------------------------------------

class RouterRequest(BaseModel):
    """Validated input from the orchestrator."""

    query: str = Field(min_length=1, max_length=2000)
    language_hint: str = Field(default="auto")
    session_id: str = Field(default="", max_length=128)
    user_role: str = Field(default="unknown", max_length=64)

    @field_validator("language_hint")
    @classmethod
    def _norm_lang_hint(cls, v: str) -> str:
        v = (v or "auto").lower().strip()
        return v if v in ("kn", "en", "auto") else "auto"


class RouterLLMOutput(BaseModel):
    """Schema the LLM must conform to. Anything else gets rejected."""

    intent: str
    entities: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=500)

    @field_validator("intent")
    @classmethod
    def _coerce_intent(cls, v: str) -> str:
        v = (v or "").strip().lower()
        # Collapse semantic_query -> lookup (RAG is a kind of lookup, and
        # the spec restricts the public intent set to the 7 listed labels).
        if v == "semantic_query":
            return "lookup"
        if v not in ALLOWED_INTENTS:
            raise ValueError(f"intent '{v}' not in {sorted(ALLOWED_INTENTS)}")
        return v


class RouterResponse(BaseModel):
    """Final response envelope returned to the caller."""

    intent: str
    language: str
    entities: dict[str, Any]
    confidence: float
    reasoning: str
    router_latency_ms: int
    request_id: str


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(query: str, hint: str) -> str:
    """Return 'kn' or 'en'. Hint wins when explicit; 'auto' uses script check.

    We treat ANY presence of Kannada Unicode codepoints as Kannada — this is
    correct for our use-case because investigators rarely sprinkle a single
    Kannada word into an otherwise-English sentence. The Voice path (Gemini
    Live API) already handles code-mixed transcription.
    """
    if hint in ("kn", "en"):
        return hint
    if _KANNADA_RE.search(query):
        return "kn"
    return "en"


# ---------------------------------------------------------------------------
# LLM JSON parsing — robust to a few common quirks
# ---------------------------------------------------------------------------

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_llm_json(text: str) -> dict:
    """Extract the first JSON object from an LLM response.

    Qwen sometimes wraps JSON in ```json fences despite the system prompt.
    We strip fences, then fall back to a greedy {...} regex if the whole
    string doesn't parse.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty LLM response")

    # Strip common code-fence wrappers
    if text.startswith("```"):
        # ```json ... ```  or  ``` ... ```
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            raise
        return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# Fallback heuristic — last-ditch keyword classifier
# ---------------------------------------------------------------------------

def _heuristic_route(query: str, language: str) -> RouterLLMOutput:
    """Deterministic keyword router used only when BOTH LLMs fail.

    Confidence is intentionally capped at 0.45 so downstream code knows
    this is a guess. Better to surface low confidence than hallucinate.
    """
    q = query.lower()

    # Meta queries first — they have very distinctive phrasing.
    if any(w in q for w in ("why did you", "explain previous", "how do you know")):
        return RouterLLMOutput(
            intent="meta_query",
            entities={"target": "previous_answer"},
            confidence=0.45,
            reasoning="Heuristic fallback: self-referential phrase detected.",
        )

    # Graph signals
    if any(w in q for w in ("connected to", "linked to", "associat", "network of", "knows ")):
        return RouterLLMOutput(
            intent="graph_query",
            entities={},
            confidence=0.40,
            reasoning="Heuristic fallback: relationship/network phrase detected.",
        )

    # Predictive signals
    if any(w in q for w in ("will ", "next week", "predict", "forecast", "trend")):
        return RouterLLMOutput(
            intent="predictive_query",
            entities={},
            confidence=0.40,
            reasoning="Heuristic fallback: future-tense/forecast phrase detected.",
        )

    # Geo signals (English + Kannada 'where')
    if any(w in q for w in ("where", "hotspot", "near ", "map of")) or "ಎಲ್ಲಿ" in query:
        return RouterLLMOutput(
            intent="geo_query",
            entities={},
            confidence=0.40,
            reasoning="Heuristic fallback: location/where phrase detected.",
        )

    # Single-FIR lookup (e.g. "FIR 2024/MG/0823")
    if re.search(r"\bfir\s*[-_/0-9a-z]{4,}", q):
        return RouterLLMOutput(
            intent="lookup",
            entities={},
            confidence=0.45,
            reasoning="Heuristic fallback: FIR identifier detected.",
        )

    # Default — treat as tabular (most common investigator query).
    return RouterLLMOutput(
        intent="tabular_query",
        entities={},
        confidence=0.30,
        reasoning="Heuristic fallback: no strong signal, defaulting to tabular.",
    )


# ---------------------------------------------------------------------------
# Core routing logic
# ---------------------------------------------------------------------------

def _call_llm(prompt_payload: dict) -> tuple[str, str]:
    """Call QuickML, falling back to Gemini. Returns (raw_text, model_label).

    Raises only if BOTH paths fail — the caller then uses the heuristic.
    """
    # Try Catalyst QuickML first
    try:
        text = catalyst_client.quickml_chat(
            system=prompt_payload["system"],
            user=prompt_payload["user"],
            temperature=prompt_payload.get("temperature", 0.1),
            max_tokens=prompt_payload.get("max_tokens", 256),
            response_format=prompt_payload.get("response_format"),
            timeout_s=_ROUTER_TIMEOUT_S,
        )
        return text, f"quickml:{catalyst_client.QUICKML_ROUTER_MODEL}"
    except catalyst_client.CatalystClientError as exc:
        logger.warning("QuickML router call failed, falling back: %s", exc)

    # Fallback: Gemini 2.5 Pro text generation
    if _GEMINI_FALLBACK and gemini_client is not None:
        try:
            text_client = gemini_client.get_text_client()
            out = text_client.generate(
                prompt_payload["user"],
                system=prompt_payload["system"],
                temperature=prompt_payload.get("temperature", 0.1),
                max_output_tokens=prompt_payload.get("max_tokens", 256),
                response_mime_type="application/json",
            )
            return out, f"gemini:{text_client.model}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini fallback also failed: %s", exc)

    raise RuntimeError("both QuickML and Gemini fallbacks failed")


def route(req: RouterRequest) -> RouterResponse:
    """End-to-end routing for one query."""
    started = time.perf_counter()
    request_id = str(uuid.uuid4())

    language = detect_language(req.query, req.language_hint)
    prompt_payload = prompts.router_prompt(req.query, language)

    model_label = "heuristic"
    decision: RouterLLMOutput

    try:
        raw_text, model_label = _call_llm(prompt_payload)
        parsed = _parse_llm_json(raw_text)
        decision = RouterLLMOutput(**parsed)
    except (ValidationError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        logger.warning(
            "LLM router parse/validation failed (request_id=%s): %s — using heuristic",
            request_id,
            exc,
        )
        decision = _heuristic_route(req.query, language)
        model_label = f"heuristic-after:{model_label}"

    # Confidence floor — surface low-confidence as `lookup` (safe default).
    if decision.confidence < _MIN_CONFIDENCE and decision.intent != "meta_query":
        logger.info(
            "Low confidence (%.2f) for intent=%s — keeping label but flagging.",
            decision.confidence,
            decision.intent,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)

    # Best-effort audit log. Never fatal — log_audit swallows its own errors.
    try:
        catalyst_client.log_audit(
            user_id=req.session_id or "anonymous",
            role=req.user_role,
            query=req.query,
            intent=decision.intent,
            sql=None,
            response="",
            latency_ms=latency_ms,
            language=language,
            confidence=decision.confidence,
            request_id=request_id,
            extra={
                "stage": "intent_router",
                "model": model_label,
                "prompt_version": prompts.PROMPT_VERSION,
                "entities": decision.entities,
                "reasoning": decision.reasoning,
                "language_hint": req.language_hint,
            },
        )
    except Exception as exc:  # noqa: BLE001 — audit must not break the response
        logger.warning("audit_log invocation raised (suppressed): %s", exc)

    return RouterResponse(
        intent=decision.intent,
        language=language,
        entities=decision.entities,
        confidence=round(decision.confidence, 3),
        reasoning=decision.reasoning,
        router_latency_ms=latency_ms,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Flask app — Catalyst Advanced I/O runs a WSGI app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/", methods=["POST"])
@app.route("/route", methods=["POST"])
def handle_route():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "invalid_json", "detail": str(exc)}), 400

    try:
        req = RouterRequest(**payload)
    except ValidationError as exc:
        return jsonify({"error": "invalid_request", "detail": exc.errors()}), 422

    try:
        result = route(req)
    except Exception as exc:  # noqa: BLE001 — last-resort guard
        logger.exception("intent-router crashed: %s", exc)
        return jsonify({"error": "internal", "detail": str(exc)}), 500

    return jsonify(result.model_dump()), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "prompt_version": prompts.PROMPT_VERSION}), 200


# ---------------------------------------------------------------------------
# Catalyst handler entry point
# ---------------------------------------------------------------------------
# Catalyst Advanced I/O Functions accept a WSGI callable as the handler.
# The platform invokes `app(environ, start_response)` directly.
handler = app


if __name__ == "__main__":
    # Local dev server: python index.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9000")), debug=True)
