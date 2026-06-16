"""Singleton Gemini client for KSP Saathi.

Wraps the google-genai SDK to expose three call paths used across functions:
  - text generation (Gemini 2.5 Pro) for premium Kannada synthesis + tool routing
  - embeddings (gemini-embedding-001) for multilingual RAG
  - Live API (bidirectional audio) for Kannada voice in/out

The Live API is the documented gap for Kannada (Catalyst Zia supports
English + Hindi only). See design.md Section 9 and decisions.md.

Environment:
    GEMINI_API_KEY   — required (or GOOGLE_API_KEY)
    GEMINI_TEXT_MODEL   — defaults to "gemini-2.5-pro"
    GEMINI_EMBED_MODEL  — defaults to "gemini-embedding-001"
    GEMINI_LIVE_MODEL   — defaults to "gemini-live-2.5-flash-preview"

All callers must reuse the singleton — instantiating fresh clients per
request defeats connection pooling.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy SDK import — google-genai may not be installed in every function bundle
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover — surfaced at call time
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]
    _GENAI_AVAILABLE = False


# Tuning knobs (env-overridable)
DEFAULT_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-pro")
DEFAULT_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
DEFAULT_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-preview")

MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
RETRY_BACKOFF_S = float(os.getenv("GEMINI_RETRY_BACKOFF_S", "0.6"))


class GeminiClientError(RuntimeError):
    """Raised when the Gemini client cannot be initialized or a call fails."""


def _require_sdk() -> None:
    if not _GENAI_AVAILABLE:
        raise GeminiClientError(
            "google-genai SDK is not installed. "
            "Add `google-genai>=0.3.0` to requirements.txt for this function."
        )


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise GeminiClientError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. "
            "See .env.example for the full list of required vars."
        )
    return key


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class _GeminiSingleton:
    """Holds one google-genai Client per process."""

    _instance: "_GeminiSingleton | None" = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        _require_sdk()
        self._client = genai.Client(api_key=_api_key())
        logger.info("GeminiClient initialized (text=%s, embed=%s, live=%s)",
                    DEFAULT_TEXT_MODEL, DEFAULT_EMBED_MODEL, DEFAULT_LIVE_MODEL)

    @classmethod
    def instance(cls) -> "_GeminiSingleton":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def client(self) -> Any:
        return self._client


# ---------------------------------------------------------------------------
# Retry helper (simple exponential backoff)
# ---------------------------------------------------------------------------

async def _with_retry_async(fn, *args, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — propagate after final attempt
            last_exc = exc
            wait = RETRY_BACKOFF_S * (2 ** attempt)
            logger.warning("Gemini call failed (attempt %d/%d): %s — retry in %.2fs",
                           attempt + 1, MAX_RETRIES, exc, wait)
            await asyncio.sleep(wait)
    raise GeminiClientError(f"Gemini call failed after {MAX_RETRIES} retries: {last_exc}")


def _with_retry_sync(fn, *args, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            import time as _t
            wait = RETRY_BACKOFF_S * (2 ** attempt)
            logger.warning("Gemini call failed (attempt %d/%d): %s — retry in %.2fs",
                           attempt + 1, MAX_RETRIES, exc, wait)
            _t.sleep(wait)
    raise GeminiClientError(f"Gemini call failed after {MAX_RETRIES} retries: {last_exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class _TextClient:
    """Thin wrapper around `client.models.generate_content` with retries."""

    def __init__(self, raw_client: Any, model: str) -> None:
        self._raw = raw_client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, *, system: str | None = None,
                 temperature: float = 0.2, max_output_tokens: int | None = None,
                 response_mime_type: str | None = None) -> str:
        """Synchronous generation returning the response text."""
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

        def _call():
            return self._raw.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )

        resp = _with_retry_sync(_call)
        return getattr(resp, "text", "") or ""

    async def generate_async(self, prompt: str, *, system: str | None = None,
                             temperature: float = 0.2,
                             max_output_tokens: int | None = None,
                             response_mime_type: str | None = None) -> str:
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

        async def _call():
            return await self._raw.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )

        resp = await _with_retry_async(_call)
        return getattr(resp, "text", "") or ""


class _EmbeddingClient:
    """Wrapper around `client.models.embed_content`."""

    def __init__(self, raw_client: Any, model: str) -> None:
        self._raw = raw_client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        if not texts:
            return []

        def _call():
            return self._raw.models.embed_content(
                model=self._model,
                contents=texts,
                config=genai_types.EmbedContentConfig(task_type=task_type),
            )

        resp = _with_retry_sync(_call)
        # google-genai returns `.embeddings` as a list of Embedding objects
        return [list(e.values) for e in resp.embeddings]

    async def embed_async(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        if not texts:
            return []

        async def _call():
            return await self._raw.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=genai_types.EmbedContentConfig(task_type=task_type),
            )

        resp = await _with_retry_async(_call)
        return [list(e.values) for e in resp.embeddings]


def get_text_client(model: str | None = None) -> _TextClient:
    """Return the text client (Gemini 2.5 Pro by default)."""
    singleton = _GeminiSingleton.instance()
    return _TextClient(singleton.client, model or DEFAULT_TEXT_MODEL)


def get_embedding_client(model: str | None = None) -> _EmbeddingClient:
    """Return the embedding client (gemini-embedding-001 by default)."""
    singleton = _GeminiSingleton.instance()
    return _EmbeddingClient(singleton.client, model or DEFAULT_EMBED_MODEL)


@asynccontextmanager
async def get_live_session(
    config: dict[str, Any] | None = None,
    *,
    model: str | None = None,
) -> AsyncIterator[Any]:
    """Async context manager yielding an open Gemini Live session.

    Typical usage (Kannada voice):

        async with get_live_session({
            "response_modalities": ["AUDIO"],
            "speech_config": {"language_code": "kn-IN"},
        }) as session:
            await session.send_realtime_input(audio=pcm_chunk)
            async for resp in session.receive():
                ...

    The default config targets Kannada audio in / audio out, which is the
    primary justified use of Gemini in this project (Catalyst Zia has no
    Kannada support — see design.md §9.3).
    """
    _require_sdk()
    singleton = _GeminiSingleton.instance()
    chosen_model = model or DEFAULT_LIVE_MODEL

    default_config: dict[str, Any] = {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "language_code": "kn-IN",
        },
    }
    if config:
        default_config.update(config)

    live_cfg = genai_types.LiveConnectConfig(**default_config) if hasattr(
        genai_types, "LiveConnectConfig"
    ) else default_config

    session_cm = singleton.client.aio.live.connect(model=chosen_model, config=live_cfg)
    try:
        async with session_cm as session:
            logger.info("Gemini Live session opened (model=%s)", chosen_model)
            yield session
    finally:
        logger.info("Gemini Live session closed (model=%s)", chosen_model)
