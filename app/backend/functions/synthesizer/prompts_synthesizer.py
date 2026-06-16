"""Synthesizer prompt templates for KSP Saathi.

Two languages — English and Kannada — with strict source-grounding rules:

  * Every claim must be traceable to a tool result (FIR id, station, graph
    edge, RAG chunk, forecast row). If a synthesized claim cannot be cited
    the model is instructed to say so rather than hallucinate.
  * The model must emit a final ``<viz>`` JSON block describing how the UI
    should update the map / network graph / chart panels.
  * Kannada output uses native Devanagari-free Kannada script (no
    transliteration). Bilingual / code-mixed input is normalised to the
    user's preferred response language declared in ``lang``.

Shared with the synthesizer Catalyst Function (``index.py``) and with the
audit logger when it replays a turn for compliance review.

Re-exported from ``shared.prompts`` via::

    from shared.prompts import synthesizer_prompt
"""

from __future__ import annotations

import json
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# System instructions
# ---------------------------------------------------------------------------

SYSTEM_EN = """You are KSP Saathi — the AI companion for Karnataka State \
Police investigators. You answer in clear, professional English suited to a \
Police Sub-Inspector / Inspector / DySP / SCRB Analyst.

GROUNDING RULES (non-negotiable):
1. Every factual claim MUST cite a source id from the tool_results — e.g.
   [FIR-2024-BLR-001234], [graph:node_42], [rag:chunk_id]. If you cannot
   cite, say "I do not have enough data to answer that" — never invent.
2. Predictive results MUST include the confidence interval and a caveat
   that the output is a resource-allocation hint, not a determinative
   prediction about any individual.
3. Never disclose features excluded for bias safety (caste, religion,
   community). If the user asks about them, refuse and explain.
4. PII (phone numbers, exact addresses, accused minor names) must be
   masked as ``***`` unless the role permits — the tool_results have
   already been role-filtered, so just preserve the masking.

OUTPUT FORMAT:
  - First, a short answer paragraph (<= 120 words).
  - Then a structured bullet list of the key findings with inline source
    citations in square brackets.
  - Finally a single ``<viz>{...}</viz>`` block (valid JSON) describing
    map markers, network graph nodes/edges, and chart series to render.
    Use the schema documented in the user message. Emit ``"map": null``
    (etc.) when a panel should be cleared.
"""


SYSTEM_KN = """ನೀವು KSP ಸಾಥಿ — ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ ತನಿಖಾಧಿಕಾರಿಗಳ \
AI ಸಹಾಯಕ. ಸಬ್-ಇನ್‌ಸ್ಪೆಕ್ಟರ್ / ಇನ್‌ಸ್ಪೆಕ್ಟರ್ / DySP / SCRB ವಿಶ್ಲೇಷಕರಿಗೆ \
ಸ್ಪಷ್ಟ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.

ಆಧಾರ ನಿಯಮಗಳು (ಬಿಡಲಾಗದು):
1. ಪ್ರತಿ ಸತ್ಯಾಂಶವೂ tool_results ನಿಂದ ಮೂಲ ಸಂದರ್ಭವನ್ನು ಉಲ್ಲೇಖಿಸಬೇಕು — \
   ಉದಾ. [FIR-2024-BLR-001234], [graph:node_42]. ಮೂಲವಿಲ್ಲದಿದ್ದರೆ \
   "ಈ ಪ್ರಶ್ನೆಗೆ ಸಾಕಷ್ಟು ಮಾಹಿತಿ ಇಲ್ಲ" ಎಂದು ಹೇಳಿ — ಎಂದಿಗೂ ಊಹಿಸಬೇಡಿ.
2. ಭವಿಷ್ಯವಾಣಿ ಫಲಿತಾಂಶಗಳಲ್ಲಿ ವಿಶ್ವಾಸ ಮಿತಿ ಮತ್ತು "ಇದು ಸಂಪನ್ಮೂಲ \
   ಹಂಚಿಕೆ ಸಲಹೆ ಮಾತ್ರ, ವ್ಯಕ್ತಿಯ ಮೇಲಿನ ಖಚಿತ ಭವಿಷ್ಯವಾಣಿ ಅಲ್ಲ" ಎಂಬ \
   ಎಚ್ಚರಿಕೆಯನ್ನು ಸೇರಿಸಬೇಕು.
3. ಜಾತಿ, ಧರ್ಮ, ಸಮುದಾಯ — ಪಕ್ಷಪಾತದ ಸುರಕ್ಷತೆಗಾಗಿ ಹೊರಗಿಡಲಾದ ಲಕ್ಷಣಗಳು. \
   ಬಳಕೆದಾರ ಕೇಳಿದರೆ ನಯವಾಗಿ ನಿರಾಕರಿಸಿ.
4. ವೈಯಕ್ತಿಕ ಮಾಹಿತಿ (ಫೋನ್, ವಿಳಾಸ, ಅಪ್ರಾಪ್ತ ಆರೋಪಿ ಹೆಸರು) ``***`` ಆಗಿ \
   ಮಸ್ಕ್ ಮಾಡಿರಬೇಕು — tool_results ನಲ್ಲಿ ಈಗಾಗಲೇ ಫಿಲ್ಟರ್ ಮಾಡಲಾಗಿದೆ.

ಔಟ್‌ಪುಟ್ ಸ್ವರೂಪ:
  - ಮೊದಲು ಚಿಕ್ಕ ಉತ್ತರ ಪ್ಯಾರಾಗ್ರಾಫ್ (<= 120 ಪದಗಳು).
  - ನಂತರ ಪ್ರಮುಖ ಸಂಶೋಧನೆಗಳ ಬುಲೆಟ್ ಪಟ್ಟಿ, ಪ್ರತಿಯೊಂದರ ಪಕ್ಕದಲ್ಲಿ ಚೌಕಾಕಾರ \
    ಬ್ರಾಕೆಟ್‌ನಲ್ಲಿ ಮೂಲ ಉಲ್ಲೇಖ.
  - ಕೊನೆಯಲ್ಲಿ ಒಂದು ``<viz>{...}</viz>`` ಬ್ಲಾಕ್ (ಮಾನ್ಯ JSON) — ನಕ್ಷೆ, \
    ನೆಟ್‌ವರ್ಕ್ ಗ್ರಾಫ್, ಚಾರ್ಟ್ ನವೀಕರಣ ವಿವರಗಳೊಂದಿಗೆ.
"""


# ---------------------------------------------------------------------------
# Viz spec schema documentation (sent in every user message)
# ---------------------------------------------------------------------------

VIZ_SCHEMA_DOC = """Viz spec JSON schema (emit inside <viz>...</viz>):

{
  "map": {
    "center": {"lat": <float>, "lng": <float>},
    "zoom": <int 5..18>,
    "markers": [
      {"id": "<source_id>", "lat": <f>, "lng": <f>,
       "label": "<short>", "severity": "low|med|high"}
    ],
    "heatmap": [{"lat": <f>, "lng": <f>, "weight": <f>}] | null
  } | null,
  "graph": {
    "nodes": [{"id": "<src>", "label": "<name>",
               "type": "person|fir|station", "centrality": <0..1>}],
    "edges": [{"source": "<id>", "target": "<id>",
               "type": "KNOWS|CO_ACCUSED_IN|CALLS|LIVES_NEAR",
               "weight": <0..1>}]
  } | null,
  "chart": {
    "kind": "line|bar|area",
    "x_label": "<str>",
    "y_label": "<str>",
    "series": [{"name": "<str>",
                 "points": [{"x": "<str|num>", "y": <num>,
                              "ci_low": <num>?, "ci_high": <num>?}]}]
  } | null
}

Emit a key as ``null`` when that panel should be CLEARED.
Omit a key entirely when the panel should be left UNCHANGED.
"""


# ---------------------------------------------------------------------------
# Few-shot examples (one English tabular, one Kannada hotspot)
# ---------------------------------------------------------------------------

_EXAMPLE_EN = """### Example — English tabular query

QUERY: How many chain snatchings near Indiranagar metro in the last 30 days?

TOOL RESULTS:
[
  {"tool": "sql", "rows": [
    {"fir_no": "FIR-2026-BLR-101", "station": "Indiranagar PS",
     "date": "2026-05-22", "lat": 12.9719, "lng": 77.6412},
    {"fir_no": "FIR-2026-BLR-118", "station": "Indiranagar PS",
     "date": "2026-06-02", "lat": 12.9722, "lng": 77.6398},
    {"fir_no": "FIR-2026-BLR-127", "station": "HAL PS",
     "date": "2026-06-09", "lat": 12.9695, "lng": 77.6442}
  ]}
]

ANSWER:
3 chain-snatching FIRs were registered within 1 km of Indiranagar metro \
between 17 May 2026 and 16 Jun 2026. Two were filed at Indiranagar PS and \
one at the adjacent HAL PS — suggesting a cross-station MO worth a joint \
review.

Key findings:
- 22 May 2026, Indiranagar PS [FIR-2026-BLR-101]
- 02 Jun 2026, Indiranagar PS [FIR-2026-BLR-118]
- 09 Jun 2026, HAL PS [FIR-2026-BLR-127]

<viz>{"map":{"center":{"lat":12.9719,"lng":77.6412},"zoom":15,"markers":[\
{"id":"FIR-2026-BLR-101","lat":12.9719,"lng":77.6412,"label":"22 May","severity":"med"},\
{"id":"FIR-2026-BLR-118","lat":12.9722,"lng":77.6398,"label":"02 Jun","severity":"med"},\
{"id":"FIR-2026-BLR-127","lat":12.9695,"lng":77.6442,"label":"09 Jun","severity":"med"}],\
"heatmap":null},"graph":null,"chart":null}</viz>
"""


_EXAMPLE_KN = """### Example — Kannada hotspot query

QUERY: ಕಳೆದ 30 ದಿನಗಳಲ್ಲಿ ಇಂದಿರಾನಗರ ಮೆಟ್ರೋ ಬಳಿ ಎಷ್ಟು ಚೈನ್ ಸ್ನಾಚಿಂಗ್ ಪ್ರಕರಣಗಳು?

TOOL RESULTS:
[
  {"tool": "sql", "rows": [
    {"fir_no": "FIR-2026-BLR-101", "station": "ಇಂದಿರಾನಗರ PS",
     "date": "2026-05-22", "lat": 12.9719, "lng": 77.6412},
    {"fir_no": "FIR-2026-BLR-118", "station": "ಇಂದಿರಾನಗರ PS",
     "date": "2026-06-02", "lat": 12.9722, "lng": 77.6398}
  ]}
]

ANSWER:
ಕಳೆದ 30 ದಿನಗಳಲ್ಲಿ ಇಂದಿರಾನಗರ ಮೆಟ್ರೋದಿಂದ 1 ಕಿ.ಮೀ. ವ್ಯಾಪ್ತಿಯಲ್ಲಿ 2 \
ಸರಪಳಿ-ಕದಿಯುವಿಕೆ ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ. ಎರಡೂ ಇಂದಿರಾನಗರ ಠಾಣೆಯಲ್ಲಿ.

ಪ್ರಮುಖ ಅಂಶಗಳು:
- 22 ಮೇ 2026, ಇಂದಿರಾನಗರ ಠಾಣೆ [FIR-2026-BLR-101]
- 02 ಜೂನ್ 2026, ಇಂದಿರಾನಗರ ಠಾಣೆ [FIR-2026-BLR-118]

<viz>{"map":{"center":{"lat":12.9720,"lng":77.6405},"zoom":15,"markers":[\
{"id":"FIR-2026-BLR-101","lat":12.9719,"lng":77.6412,"label":"22 ಮೇ","severity":"med"},\
{"id":"FIR-2026-BLR-118","lat":12.9722,"lng":77.6398,"label":"02 ಜೂನ್","severity":"med"}],\
"heatmap":null},"graph":null,"chart":null}</viz>
"""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def _normalize_lang(lang: str | None) -> str:
    if not lang:
        return "en"
    lang = lang.lower().strip()
    if lang.startswith("kn"):
        return "kn"
    return "en"


def _safe_json(value: Any) -> str:
    """Compact JSON dump that never raises on exotic objects."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def system_instruction(lang: str) -> str:
    """Pick the right system prompt for the synthesizer."""
    return SYSTEM_KN if _normalize_lang(lang) == "kn" else SYSTEM_EN


def synthesizer_prompt(
    query: str,
    lang: str,
    tool_results: Iterable[dict[str, Any]] | None,
    *,
    router_decision: dict[str, Any] | None = None,
    include_examples: bool = True,
) -> str:
    """Build the user-message portion of the synthesizer prompt.

    The system instruction is returned separately by ``system_instruction``
    so that the LLM client can pass it via the ``system`` parameter.

    Parameters
    ----------
    query:
        The raw investigator utterance (already STT-decoded).
    lang:
        ``"en"`` or ``"kn"`` — chooses the response language and example set.
    tool_results:
        List of tool result envelopes from the orchestrator.
    router_decision:
        Optional intent-router output; included so the model knows which
        tools were attempted and why.
    include_examples:
        Whether to embed the few-shot exemplar. Set ``False`` for callers
        that need a shorter prompt (e.g. Qwen 2.5 14B at small context).
    """
    lang = _normalize_lang(lang)
    tool_block = _safe_json(list(tool_results) if tool_results else [])
    router_block = _safe_json(router_decision) if router_decision else "null"

    example_block = ""
    if include_examples:
        example_block = _EXAMPLE_KN if lang == "kn" else _EXAMPLE_EN
        example_block = "\n" + example_block.strip() + "\n"

    response_lang_note = (
        "Respond in Kannada (kn-IN script). Do not transliterate."
        if lang == "kn"
        else "Respond in English."
    )

    return (
        f"{VIZ_SCHEMA_DOC.strip()}\n"
        f"{example_block}\n"
        "### Now answer the live query\n\n"
        f"USER QUERY ({lang}): {query.strip()}\n\n"
        f"ROUTER DECISION: {router_block}\n\n"
        f"TOOL RESULTS: {tool_block}\n\n"
        f"INSTRUCTIONS: {response_lang_note} "
        "Cite every claim. End with exactly one <viz>{...}</viz> block "
        "containing valid JSON per the schema above."
    )


__all__ = [
    "SYSTEM_EN",
    "SYSTEM_KN",
    "VIZ_SCHEMA_DOC",
    "synthesizer_prompt",
    "system_instruction",
]
