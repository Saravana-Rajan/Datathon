"use client";

/**
 * Voice Activity Detection hook — wraps @ricky0123/vad-web (Silero VAD,
 * runs in an AudioWorklet so the main thread stays responsive).
 *
 * Lifecycle:
 *   1. start()     — request mic permission, spin up the worker.
 *   2. onSpeechStart → caller pre-warms its STT session.
 *   3. onFrameProcessed → caller streams audio (Float32) to STT.
 *   4. onSpeechEnd  — caller finalizes the utterance.
 *   5. pause() / stop() — barge-in or teardown.
 *
 * Why a custom hook rather than calling MicVAD directly: we want
 *   - a single source of mic state (no double prompts)
 *   - SSR safety (vad-web pulls in WASM that breaks under Node)
 *   - volume metering surfaced to the UI without exposing the worker.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { rmsVolume } from "@/lib/audio";

export type VadStatus =
  | "idle"
  | "loading"
  | "ready"
  | "listening"
  | "speaking"
  | "error";

export type MicPermission = "unknown" | "granted" | "denied" | "prompt";

export interface UseVADOptions {
  /** ms of silence after speech before onSpeechEnd fires. Default 200ms. */
  silenceMs?: number;
  /** Probability above which a frame is "voice". Default 0.5. */
  positiveSpeechThreshold?: number;
  /** Probability below which a frame is "silence". Default 0.35. */
  negativeSpeechThreshold?: number;
  /** Minimum utterance length in frames to fire onSpeechEnd. Default 4. */
  minSpeechFrames?: number;
  /** Called once a continuous speech segment is detected. */
  onSpeechStart?: () => void;
  /** Called when silence has held for `silenceMs` after a speech segment. */
  onSpeechEnd?: (audio: Float32Array) => void;
  /** Per-frame callback while VAD is running. ~30ms cadence. */
  onFrame?: (frame: Float32Array, isSpeech: boolean, volume: number) => void;
  /** Surfaces underlying errors (mic denied, worker failed, etc.). */
  onError?: (err: Error) => void;
  /** Auto-load the worker on mount. Default false — caller usually waits for user gesture. */
  autoLoad?: boolean;
}

export interface UseVADReturn {
  status: VadStatus;
  permission: MicPermission;
  volume: number;
  errorMessage: string | null;
  /** Idempotent — safe to call before user gesture. */
  load: () => Promise<void>;
  /** Begin listening (mic open + VAD running). */
  start: () => Promise<void>;
  /** Stop listening. Releases the mic stream. */
  stop: () => Promise<void>;
  /** Temporarily pause without releasing mic — used during TTS playback. */
  pause: () => void;
  resume: () => void;
}

// Minimal structural typing of vad-web's MicVAD. We avoid `any` and we don't
// rely on the library's TS types being present at install time.
interface MicVadInstance {
  start: () => void;
  pause: () => void;
  destroy: () => void | Promise<void>;
}

interface MicVadOptions {
  positiveSpeechThreshold: number;
  negativeSpeechThreshold: number;
  minSpeechFrames: number;
  redemptionFrames: number;
  preSpeechPadFrames?: number;
  onSpeechStart?: () => void;
  onSpeechEnd?: (audio: Float32Array) => void;
  onFrameProcessed?: (
    probs: { isSpeech: number; notSpeech: number },
    frame: Float32Array,
  ) => void;
  onVADMisfire?: () => void;
  model?: "v5" | "legacy";
}

interface MicVadStatic {
  new: (opts: MicVadOptions) => Promise<MicVadInstance>;
}

interface VadWebModule {
  MicVAD: MicVadStatic;
}

/** vad-web emits frames every 32ms at 16kHz (≈512 samples). */
const FRAME_MS = 32;

export function useVAD(options: UseVADOptions = {}): UseVADReturn {
  const {
    silenceMs = 200,
    positiveSpeechThreshold = 0.5,
    negativeSpeechThreshold = 0.35,
    minSpeechFrames = 4,
    onSpeechStart,
    onSpeechEnd,
    onFrame,
    onError,
    autoLoad = false,
  } = options;

  const [status, setStatus] = useState<VadStatus>("idle");
  const [permission, setPermission] = useState<MicPermission>("unknown");
  const [volume, setVolume] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const vadRef = useRef<MicVadInstance | null>(null);
  const pausedRef = useRef(false);
  const loadPromiseRef = useRef<Promise<void> | null>(null);

  // Keep callbacks fresh without re-creating the worker.
  const cbRef = useRef({ onSpeechStart, onSpeechEnd, onFrame, onError });
  useEffect(() => {
    cbRef.current = { onSpeechStart, onSpeechEnd, onFrame, onError };
  }, [onSpeechStart, onSpeechEnd, onFrame, onError]);

  const emitError = useCallback((err: unknown) => {
    const e = err instanceof Error ? err : new Error(String(err));
    setStatus("error");
    setErrorMessage(e.message);
    cbRef.current.onError?.(e);
  }, []);

  // Sync permission state from the Permissions API where available.
  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.permissions) return;
    let cancelled = false;
    (async () => {
      try {
        const status = await navigator.permissions.query({
          name: "microphone" as PermissionName,
        });
        if (cancelled) return;
        setPermission(status.state as MicPermission);
        status.onchange = () => {
          setPermission(status.state as MicPermission);
        };
      } catch {
        // Some browsers (Firefox <=126) don't support querying mic permission.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async (): Promise<void> => {
    if (vadRef.current) return;
    if (loadPromiseRef.current) return loadPromiseRef.current;
    if (typeof window === "undefined") return;

    setStatus("loading");
    setErrorMessage(null);

    const redemptionFrames = Math.max(1, Math.round(silenceMs / FRAME_MS));

    loadPromiseRef.current = (async () => {
      try {
        // Dynamic import — vad-web pulls in WASM which can't be SSR'd.
        const mod = (await import("@ricky0123/vad-web")) as unknown as VadWebModule;
        const instance = await mod.MicVAD.new({
          positiveSpeechThreshold,
          negativeSpeechThreshold,
          minSpeechFrames,
          redemptionFrames,
          preSpeechPadFrames: 8,
          model: "v5",
          onSpeechStart: () => {
            setStatus("speaking");
            cbRef.current.onSpeechStart?.();
          },
          onSpeechEnd: (audio: Float32Array) => {
            setStatus(pausedRef.current ? "ready" : "listening");
            cbRef.current.onSpeechEnd?.(audio);
          },
          onFrameProcessed: (probs, frame) => {
            const vol = rmsVolume(frame);
            setVolume(vol);
            const isSpeech = probs.isSpeech >= positiveSpeechThreshold;
            cbRef.current.onFrame?.(frame, isSpeech, vol);
          },
          onVADMisfire: () => {
            // False-alarm speech — return to listening.
            setStatus(pausedRef.current ? "ready" : "listening");
          },
        });
        vadRef.current = instance;
        setStatus("ready");
        setPermission("granted");
      } catch (err) {
        // Distinguish permission errors from generic failures so the UI can
        // render the right "enable mic" message.
        const msg = err instanceof Error ? err.message : String(err);
        if (/permission|denied|NotAllowed/i.test(msg)) {
          setPermission("denied");
        }
        loadPromiseRef.current = null;
        emitError(err);
        throw err;
      }
    })();
    return loadPromiseRef.current;
  }, [
    silenceMs,
    positiveSpeechThreshold,
    negativeSpeechThreshold,
    minSpeechFrames,
    emitError,
  ]);

  const start = useCallback(async () => {
    if (!vadRef.current) {
      await load();
    }
    if (!vadRef.current) return;
    pausedRef.current = false;
    try {
      vadRef.current.start();
      setStatus("listening");
    } catch (err) {
      emitError(err);
    }
  }, [load, emitError]);

  const stop = useCallback(async () => {
    pausedRef.current = false;
    if (vadRef.current) {
      try {
        await vadRef.current.destroy();
      } catch {
        /* ignore */
      }
      vadRef.current = null;
    }
    loadPromiseRef.current = null;
    setStatus("idle");
    setVolume(0);
  }, []);

  const pause = useCallback(() => {
    pausedRef.current = true;
    if (vadRef.current) {
      try {
        vadRef.current.pause();
      } catch {
        /* already paused */
      }
    }
    setStatus("ready");
  }, []);

  const resume = useCallback(() => {
    pausedRef.current = false;
    if (vadRef.current) {
      try {
        vadRef.current.start();
        setStatus("listening");
      } catch (err) {
        emitError(err);
      }
    }
  }, [emitError]);

  useEffect(() => {
    if (autoLoad) {
      void load();
    }
    return () => {
      if (vadRef.current) {
        void vadRef.current.destroy();
        vadRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { status, permission, volume, errorMessage, load, start, stop, pause, resume };
}
