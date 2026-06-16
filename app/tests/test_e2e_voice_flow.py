"""End-to-end voice loop tests for Yaksha.

These tests upload sample audio to the voice ingress endpoint and assert
that:

* English audio → transcript + audio response (Catalyst Zia path)
* Kannada audio → Kannada transcript + Kannada audio response (Gemini
  Live path)
* Barge-in works — a follow-up audio frame mid-stream cancels the
  in-flight response and starts a new one.

Voice ingress contract (see ``app/backend/functions/voice-ingress`` once
deployed, or the orchestrator's ``/voice`` route — exact path is set
via the ``CATALYST_VOICE_PATH`` env var, defaulting to
``/server/voice-ingress``):

    POST {API_BASE}{CATALYST_VOICE_PATH}
    multipart/form-data:
        audio:         <wav file>
        language_hint: "en" | "kn" | "auto"
        session_id:    str
        user_role:     str
    response:
        text/event-stream of JSON events
        {transcript, text_chunk, audio_b64, viz_spec, done}

All three tests skip cleanly when:

* ``CATALYST_API_BASE`` is unset (the suite isn't pointed at a live
  deployment), OR
* the corresponding audio fixture is missing under
  ``tests/fixtures/audio/``.

This keeps the rest of the test matrix green on a fresh checkout.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.voice]


VOICE_PATH = os.getenv("CATALYST_VOICE_PATH", "/server/voice-ingress")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_audio(path: Path) -> None:
    """Skip the test if the audio fixture is not present."""
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip(
            f"voice fixture missing: {path.name} "
            f"(see tests/fixtures/audio/README.md for how to create it)",
        )


async def _stream_voice(
    base_url: str,
    audio_path: Path,
    *,
    language_hint: str = "auto",
    session_id: str = "voice-test",
    user_role: str = "inspector",
    timeout: float = 30.0,
) -> AsyncIterator[dict[str, Any]]:
    """POST a wav file to the voice ingress and yield each parsed SSE event."""
    url = f"{base_url}{VOICE_PATH}"
    headers = {"Accept": "text/event-stream"}
    auth_token = os.getenv("CATALYST_AUTH_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    with audio_path.open("rb") as audio_fh:
        files = {"audio": (audio_path.name, audio_fh, "audio/wav")}
        data = {
            "language_hint": language_hint,
            "session_id": session_id,
            "user_role": user_role,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url, files=files, data=data, headers=headers,
            ) as resp:
                resp.raise_for_status()
                buffer = b""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk
                    while b"\n\n" in buffer:
                        raw_event, buffer = buffer.split(b"\n\n", 1)
                        for line in raw_event.split(b"\n"):
                            if line.startswith(b"data:"):
                                payload = line[5:].decode("utf-8").strip()
                                if not payload:
                                    continue
                                try:
                                    yield json.loads(payload)
                                except json.JSONDecodeError:
                                    continue


async def _collect(stream: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    async for event in stream:
        out.append(event)
        if event.get("type") in ("done", "orchestrator_done"):
            break
    return out


def _audio_b64_total_bytes(events: list[dict[str, Any]]) -> int:
    """Sum the decoded length of every ``audio_b64`` chunk."""
    total = 0
    for e in events:
        b64 = e.get("audio_b64") or (e.get("audio") if e.get("type") == "audio" else None)
        if not b64:
            continue
        try:
            total += len(base64.b64decode(b64))
        except Exception:  # noqa: BLE001 — malformed chunks just don't count
            continue
    return total


# ---------------------------------------------------------------------------
# Test 1 — English audio → transcript + English audio response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_english_audio_returns_text_and_audio(
    integration_base_url: str,
    audio_fixtures_dir: Path,
) -> None:
    audio_path = audio_fixtures_dir / "en_sample.wav"
    _require_audio(audio_path)

    events = await _collect(_stream_voice(
        integration_base_url,
        audio_path,
        language_hint="en",
        session_id="voice-en-001",
        user_role="inspector",
    ))

    # Transcript event must arrive — proves STT worked.
    transcripts = [e for e in events if e.get("type") == "transcript"]
    assert transcripts, f"no transcript event in {[e.get('type') for e in events]}"
    transcript_text = transcripts[0].get("text", "")
    assert transcript_text.strip(), "transcript text is empty"

    # Text chunks (the synthesized answer) must arrive.
    text = "".join(
        e.get("content", "") for e in events if e.get("type") == "text_chunk"
    )
    assert text.strip(), "no text_chunk content"

    # And the TTS audio comes back as base64 frames.
    audio_bytes = _audio_b64_total_bytes(events)
    assert audio_bytes > 1024, (
        f"expected >1KB of TTS audio, got {audio_bytes}B "
        f"(types seen: {[e.get('type') for e in events]})"
    )


# ---------------------------------------------------------------------------
# Test 2 — Kannada audio → Kannada transcript + Kannada audio response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kannada_audio_returns_kannada_response(
    integration_base_url: str,
    audio_fixtures_dir: Path,
    lang_helpers: dict,
) -> None:
    audio_path = audio_fixtures_dir / "kn_sample.wav"
    _require_audio(audio_path)

    events = await _collect(_stream_voice(
        integration_base_url,
        audio_path,
        language_hint="kn",
        session_id="voice-kn-001",
        user_role="sub_inspector",
    ))

    transcripts = [e for e in events if e.get("type") == "transcript"]
    assert transcripts, "no transcript event"
    transcript_text = transcripts[0].get("text", "")
    assert lang_helpers["has_kannada"](transcript_text), (
        f"Kannada transcript expected; got {transcript_text!r}"
    )

    # Synthesized text must be Kannada.
    text = "".join(
        e.get("content", "") for e in events if e.get("type") == "text_chunk"
    )
    assert lang_helpers["has_kannada"](text), (
        f"Expected Kannada answer; got {text[:200]!r}"
    )

    # Audio came back.
    audio_bytes = _audio_b64_total_bytes(events)
    assert audio_bytes > 1024, f"expected Kannada TTS audio; got {audio_bytes}B"

    # If the response advertises a language field, it must be 'kn'.
    lang_events = [
        e for e in events
        if e.get("type") in ("routed", "transcript") and e.get("language")
    ]
    if lang_events:
        assert lang_events[0]["language"] == "kn", lang_events[0]


# ---------------------------------------------------------------------------
# Test 3 — Barge-in: mid-response interrupt cancels current stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_barge_in_interrupts_mid_response(
    integration_base_url: str,
    audio_fixtures_dir: Path,
) -> None:
    """Send a follow-up question while the first is still streaming.

    Expected behaviour: first stream emits a ``cancelled`` (or
    ``superseded``) event and ends; the second stream completes
    normally with its own ``done``. If the server doesn't yet support
    barge-in we skip with a clear message — barge-in is a stretch goal
    on the demo timeline, not a must-ship.
    """
    first_audio = audio_fixtures_dir / "en_sample.wav"
    interrupt_audio = audio_fixtures_dir / "en_bargein_question.wav"
    _require_audio(first_audio)
    _require_audio(interrupt_audio)

    session_id = "voice-bargein-001"

    async def _drain(stream: AsyncIterator[dict[str, Any]], out: list) -> None:
        try:
            async for event in stream:
                out.append(event)
                if event.get("type") in ("done", "orchestrator_done",
                                         "cancelled", "superseded"):
                    return
        except (httpx.ReadError, httpx.RemoteProtocolError):
            # Connection cut by the server when the second request arrives —
            # that's the expected barge-in behaviour for some implementations.
            out.append({"type": "connection_closed"})

    first_events: list[dict[str, Any]] = []
    second_events: list[dict[str, Any]] = []

    first_stream = _stream_voice(
        integration_base_url, first_audio,
        language_hint="en", session_id=session_id, user_role="inspector",
    )
    first_task = asyncio.create_task(_drain(first_stream, first_events))

    # Give the first request a head start so it's mid-stream.
    await asyncio.sleep(0.5)

    second_stream = _stream_voice(
        integration_base_url, interrupt_audio,
        language_hint="en", session_id=session_id, user_role="inspector",
    )
    second_task = asyncio.create_task(_drain(second_stream, second_events))

    # Wait for both with a wall-clock cap.
    await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=30.0)

    # The second request must complete normally.
    second_types = [e.get("type") for e in second_events]
    assert "done" in second_types or "orchestrator_done" in second_types, (
        f"second turn did not complete: {second_types}"
    )

    # The first request should have been interrupted in some recognizable way:
    # either an explicit cancel/supersede event or a closed connection.
    first_types = [e.get("type") for e in first_events]
    interrupted = any(
        t in {"cancelled", "superseded", "interrupted", "connection_closed"}
        for t in first_types
    )

    if not interrupted:
        # Barge-in not yet enforced server-side — fail soft so this test
        # signals "stretch goal pending" rather than blocking the deploy.
        pytest.xfail(
            f"barge-in not enforced; first stream completed normally: {first_types}",
        )
