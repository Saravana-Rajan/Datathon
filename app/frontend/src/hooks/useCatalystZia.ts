"use client";

/**
 * Catalyst Zia STT/TTS bridge — English + Hindi voice path for Sarvik.
 *
 * Zia Services are accessed via two Catalyst Functions deployed in
 * `app/backend/functions/`:
 *   - POST /server/zia-stt   { audio: base64 wav, language: "en"|"hi" }
 *                            -> { transcript, confidence }
 *   - POST /server/zia-tts   { text, language: "en"|"hi", voice? }
 *                            -> audio/wav (binary)
 *
 * The frontend never talks to the Zia API directly — credentials live only
 * in Catalyst Function env vars (see `app/backend/functions/zia-*/`).
 *
 * Endpoint base URL is configurable via NEXT_PUBLIC_CATALYST_FUNCTIONS_URL.
 * For local dev it defaults to the Next.js API proxy under `/api/zia/*`.
 */

import { useCallback, useRef, useState } from "react";
import { pcm16ToBlob, playAudioBlob } from "@/lib/audio";

export type ZiaLanguage = "en" | "hi";

export interface ZiaSttResult {
  transcript: string;
  confidence: number;
  language: ZiaLanguage;
  latencyMs: number;
}

export interface UseCatalystZiaOptions {
  /** Base URL of the Catalyst Functions deployment. */
  baseUrl?: string;
  /** Catalyst Authentication bearer token (JWT). */
  authToken?: string;
  /** Override fetch — useful for tests / SSR. */
  fetchImpl?: typeof fetch;
}

export interface UseCatalystZiaReturn {
  /** STT: send a recorded blob, get a transcript back. */
  transcribe: (blob: Blob, language: ZiaLanguage) => Promise<ZiaSttResult>;
  /** TTS: send text, receive a WAV blob you can play. */
  synthesize: (text: string, language: ZiaLanguage) => Promise<Blob>;
  /** Convenience: synth then play, with barge-in support. */
  speak: (text: string, language: ZiaLanguage) => Promise<void>;
  /** Stop in-flight TTS playback (barge-in). */
  stopSpeaking: () => void;
  isBusy: boolean;
  lastError: string | null;
}

const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_CATALYST_FUNCTIONS_URL ?? "/api";

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("FileReader did not return a string"));
        return;
      }
      // result is "data:audio/wav;base64,XXXX" — strip the prefix.
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("FileReader failed"));
    reader.readAsDataURL(blob);
  });
}

/**
 * Ensure a blob is a WAV. Catalyst Zia accepts WAV/MP3/FLAC but the simplest
 * round-trip from MediaRecorder is to re-encode to PCM16 WAV here.
 *
 * Callers that already have PCM16 should pass it via `pcm16ToBlob` and skip
 * this helper.
 */
async function ensureWav(blob: Blob): Promise<Blob> {
  if (blob.type === "audio/wav") return blob;
  // Decode in an OfflineAudioContext and rewrap. Heavyweight but only runs
  // once per utterance — typically <100ms for 5s of audio.
  const { audioBlobToFloat32, float32ToPcm16, ZIA_SAMPLE_RATE } = await import(
    "@/lib/audio"
  );
  const float = await audioBlobToFloat32(blob, ZIA_SAMPLE_RATE);
  const pcm = float32ToPcm16(float);
  return pcm16ToBlob(pcm, ZIA_SAMPLE_RATE, 1);
}

export function useCatalystZia(
  options: UseCatalystZiaOptions = {},
): UseCatalystZiaReturn {
  const {
    baseUrl = DEFAULT_BASE_URL,
    authToken,
    fetchImpl,
  } = options;

  const [isBusy, setIsBusy] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const doFetch = useCallback(
    async (path: string, init: RequestInit): Promise<Response> => {
      const f = fetchImpl ?? fetch;
      const headers = new Headers(init.headers);
      if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const url = `${baseUrl.replace(/\/$/, "")}${path}`;
      const res = await f(url, { ...init, headers, signal: ctrl.signal });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`${path} ${res.status}: ${text || res.statusText}`);
      }
      return res;
    },
    [baseUrl, authToken, fetchImpl],
  );

  const transcribe = useCallback(
    async (blob: Blob, language: ZiaLanguage): Promise<ZiaSttResult> => {
      setIsBusy(true);
      setLastError(null);
      const t0 = performance.now();
      try {
        const wav = await ensureWav(blob);
        const base64 = await blobToBase64(wav);
        const res = await doFetch("/zia/stt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audio: base64, language, format: "wav" }),
        });
        const payload = (await res.json()) as {
          transcript: string;
          confidence?: number;
        };
        return {
          transcript: payload.transcript,
          confidence: payload.confidence ?? 0,
          language,
          latencyMs: performance.now() - t0,
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setLastError(msg);
        throw err;
      } finally {
        setIsBusy(false);
      }
    },
    [doFetch],
  );

  const synthesize = useCallback(
    async (text: string, language: ZiaLanguage): Promise<Blob> => {
      setIsBusy(true);
      setLastError(null);
      try {
        const res = await doFetch("/zia/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language, format: "wav" }),
        });
        const blob = await res.blob();
        return blob;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setLastError(msg);
        throw err;
      } finally {
        setIsBusy(false);
      }
    },
    [doFetch],
  );

  const stopSpeaking = useCallback(() => {
    if (audioElRef.current) {
      try {
        audioElRef.current.pause();
        audioElRef.current.currentTime = 0;
      } catch {
        /* ignore */
      }
    }
    if (abortRef.current) {
      try {
        abortRef.current.abort();
      } catch {
        /* ignore */
      }
    }
  }, []);

  const speak = useCallback(
    async (text: string, language: ZiaLanguage): Promise<void> => {
      const blob = await synthesize(text, language);
      if (!audioElRef.current) audioElRef.current = new Audio();
      await playAudioBlob(blob, audioElRef.current);
    },
    [synthesize],
  );

  return { transcribe, synthesize, speak, stopSpeaking, isBusy, lastError };
}
