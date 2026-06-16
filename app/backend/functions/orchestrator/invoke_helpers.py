"""Shared HTTP invocation helpers for the KSP Saathi orchestrator.

This module is the *only* place that knows how to call another Catalyst
Function over HTTP. Centralising it means:

  * Retry / timeout policy lives in one place.
  * URL resolution (explicit env var per function OR build-from-base) is
    consistent across every downstream call.
  * Streaming responses (synthesizer SSE) share the same auth + error
    handling as the unary calls (intent-router, sql-generator, ...).

Catalyst Circuits is NOT available in the India DC (see design.md §18
Decision Log 2026-06-16) — so the orchestrator Function performs the
fan-out in Python via ``httpx.AsyncClient`` instead of YAML steps.

Per-function URL resolution order:

    1. ``FN_<NAME>_URL`` env var (e.g. ``FN_INTENT_ROUTER_URL``) — the
       deploy pipeline sets this once we have stable Catalyst URLs.
    2. ``CATALYST_API_BASE`` + ``/<name>`` fallback.

Auth: every outbound request carries the ``CATALYST_TOKEN`` bearer token
so internal-only functions can refuse anything else at their edge.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator

import httpx

logger = logging.getLogger("ksp_saathi.orchestrator.invoke")

# ---------------------------------------------------------------------------
# Configuration — pulled from env so the deploy pipeline can hot-swap URLs
# ---------------------------------------------------------------------------

CATALYST_API_BASE = os.getenv(
    "CATALYST_API_BASE",
    "https://ksp-saathi-60067540097.catalystserverless.in/server",
).rstrip("/")

CATALYST_TOKEN = os.getenv("CATALYST_TOKEN", "")

# Default per-tool soft timeout. The orchestrator further enforces an
# overall 30s budget via ``asyncio.wait_for`` at the gather() boundary.
DEFAULT_TIMEOUT_S = float(os.getenv("ORCH_TOOL_TIMEOUT_S", "8.0"))

# A single transient retry on 5xx / network failures. The router itself
# also retries internally; this is the orchestrator-level safety net.
DEFAULT_RETRY_ATTEMPTS = int(os.getenv("ORCH_RETRY_ATTEMPTS", "2"))
RETRY_BACKOFF_MS = int(os.getenv("ORCH_RETRY_BACKOFF_MS", "250"))


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InvokeError(RuntimeError):
    """Base class for orchestrator-level invocation failures."""


class InvokeTimeout(InvokeError):
    """The downstream function did not respond before ``timeout`` seconds."""


class InvokeHTTPError(InvokeError):
    """The downstream function returned a non-2xx response."""

    def __init__(self, status: int, body: str, name: str) -> None:
        super().__init__(f"{name} HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body
        self.name = name


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

def resolve_url(name: str) -> str:
    """Resolve a function's HTTP endpoint.

    Convention: env var ``FN_<NAME>_URL`` with the name uppercased and
    hyphens replaced by underscores. Examples:

        intent-router      -> FN_INTENT_ROUTER_URL
        sql-generator      -> FN_SQL_GENERATOR_URL
        synthesizer        -> FN_SYNTHESIZER_URL
        audit-logger       -> FN_AUDIT_LOGGER_URL
        predictive-service -> FN_PREDICTIVE_SERVICE_URL
    """
    env_key = f"FN_{name.upper().replace('-', '_')}_URL"
    explicit = os.getenv(env_key)
    if explicit:
        return explicit.rstrip("/")
    if not CATALYST_API_BASE:
        raise InvokeError(
            f"No URL for function '{name}' — set {env_key} or CATALYST_API_BASE."
        )
    return f"{CATALYST_API_BASE}/{name}"


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if CATALYST_TOKEN:
        headers["Authorization"] = f"Bearer {CATALYST_TOKEN}"
    if extra:
        headers.update(extra)
    return headers


# ---------------------------------------------------------------------------
# Unary invocation — JSON in, JSON out, with one retry on transient errors
# ---------------------------------------------------------------------------

_TRANSIENT_STATUSES = {500, 502, 503, 504}


async def invoke_function(
    name: str,
    payload: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Call another Catalyst Function and return its JSON response.

    Args:
        name: function name (matches the folder name under ``functions/``).
        payload: JSON-serialisable request body.
        timeout: per-attempt soft timeout in seconds.
        attempts: total attempts including the first. Default 2 = 1 retry.
        client: optional shared ``httpx.AsyncClient`` (re-use the pool from
            the orchestrator so we don't pay TLS-handshake per call).

    Raises:
        InvokeTimeout: ran out of time on every attempt.
        InvokeHTTPError: final attempt returned a non-2xx response.
        InvokeError: malformed JSON or unrecoverable network failure.
    """
    url = resolve_url(name)
    last_exc: Exception | None = None

    async def _do_call(c: httpx.AsyncClient) -> dict[str, Any]:
        nonlocal last_exc
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                resp = await c.post(
                    url,
                    json=payload,
                    headers=_auth_headers(),
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "invoke_function name=%s attempt=%d/%d TIMEOUT after %.2fs",
                    name, attempt, attempts, timeout,
                )
                if attempt < attempts:
                    await asyncio.sleep(RETRY_BACKOFF_MS / 1000.0)
                    continue
                raise InvokeTimeout(f"{name} timed out after {timeout}s") from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "invoke_function name=%s attempt=%d/%d NETWORK %s",
                    name, attempt, attempts, exc,
                )
                if attempt < attempts:
                    await asyncio.sleep(RETRY_BACKOFF_MS / 1000.0)
                    continue
                raise InvokeError(f"{name} network error: {exc}") from exc

            elapsed_ms = int((time.perf_counter() - started) * 1000)

            if resp.status_code in _TRANSIENT_STATUSES and attempt < attempts:
                logger.warning(
                    "invoke_function name=%s attempt=%d/%d %d retrying",
                    name, attempt, attempts, resp.status_code,
                )
                await asyncio.sleep(RETRY_BACKOFF_MS / 1000.0)
                continue

            if resp.status_code >= 400:
                raise InvokeHTTPError(resp.status_code, resp.text, name)

            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                raise InvokeError(
                    f"{name} returned non-JSON body: {resp.text[:200]}"
                ) from exc

            logger.info(
                "invoke_function name=%s status=%d ms=%d",
                name, resp.status_code, elapsed_ms,
            )
            return data

        # Unreachable — loop either returns or raises — kept for type narrowing.
        raise InvokeError(f"{name} failed: {last_exc}")  # pragma: no cover

    if client is not None:
        return await _do_call(client)

    async with httpx.AsyncClient() as c:
        return await _do_call(c)


# ---------------------------------------------------------------------------
# Streaming invocation — used for the synthesizer SSE proxy
# ---------------------------------------------------------------------------

@asynccontextmanager
async def stream_function(
    name: str,
    payload: dict[str, Any],
    *,
    timeout: float = 60.0,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[AsyncGenerator[bytes, None]]:
    """Open a streaming HTTP response from a downstream function.

    Yields an async generator of raw bytes (one chunk per LLM delta) so
    the orchestrator can re-frame and forward each SSE event to its
    client. The synthesizer already speaks SSE — we just need to pipe
    the bytes through with minimal buffering.

    Usage:
        async with stream_function("synthesizer", body) as chunks:
            async for chunk in chunks:
                await write_to_client(chunk)
    """
    url = resolve_url(name)
    headers = _auth_headers({"Accept": "text/event-stream"})

    owns_client = client is None
    c = client or httpx.AsyncClient(timeout=timeout)

    try:
        async with c.stream("POST", url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise InvokeHTTPError(
                    resp.status_code,
                    body.decode("utf-8", errors="replace"),
                    name,
                )

            async def _bytes() -> AsyncGenerator[bytes, None]:
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        yield chunk

            yield _bytes()
    finally:
        if owns_client:
            await c.aclose()


# ---------------------------------------------------------------------------
# Fire-and-forget — used for audit-logger
# ---------------------------------------------------------------------------

async def invoke_fire_and_forget(
    name: str,
    payload: dict[str, Any],
    *,
    timeout: float = 4.0,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Best-effort invoke. Swallows every error so the caller never blocks.

    Used for audit writes: a failed audit must NOT fail the user query.
    Catalyst Signals + a reconciliation cron job pick up missed writes.
    """
    try:
        await invoke_function(name, payload, timeout=timeout, attempts=1, client=client)
    except Exception as exc:  # noqa: BLE001 — intentional swallow
        logger.warning("fire_and_forget %s suppressed: %s", name, exc)


__all__ = [
    "InvokeError",
    "InvokeHTTPError",
    "InvokeTimeout",
    "invoke_function",
    "invoke_fire_and_forget",
    "stream_function",
    "resolve_url",
    "DEFAULT_TIMEOUT_S",
]
