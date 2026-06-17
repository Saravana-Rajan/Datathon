"""Shared utilities for KSP Saathi Catalyst Functions.

Modules:
    prompts          - LLM prompt templates (router, sql, cypher, synthesizer)
    catalyst_client  - thin wrappers over zcatalyst-sdk (QuickML, NoSQL audit log)
    gemini_client    - Google Gemini fallback (used only when Catalyst QuickML fails)
"""
