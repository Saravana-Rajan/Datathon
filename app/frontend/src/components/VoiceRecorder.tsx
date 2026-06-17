"use client";

/**
 * VoiceRecorder — the user-facing mic affordance for Sarvik.
 *
 * State machine:
 *
 *     idle ──click──> requesting-permission ──ok──> listening
 *                                              │
 *                                              └─denied──> error
 *
 *     listening ──VAD speech start──> capturing
 *     capturing ──VAD silence──────> processing
 *     processing (Kannada) ──Gemini Live audio stream──> speaking
 *     processing (English) ──Zia TTS WAV──> speaking
 *     speaking ──TTS ends OR user speaks (barge-in)──> listening
 *
 * Visual language matches the rest of the Sarvik shell — Tailwind
 * primitives + Lucide icons, no extra UI deps. Designed mobile-first.
 *
 * Accessibility:
 *   - The mic button has role="button" + aria-pressed reflecting recording.
 *   - State changes announced via aria-live region.
 *   - Keyboard: Space / Enter toggles recording; Esc cancels.
 *   - Volume meter has aria-hidden — it's pure decoration.
 *
 * Performance:
 *   - VAD runs in an AudioWorklet via @ricky0123/vad-web (no main thread work).
 *   - PCM conversion uses typed arrays; no string-based base64 in hot path.
 *   - Gemini audio streams play through gap-free WebAudio scheduling.
 */

import { Loader2, Mic, MicOff, Volume2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useGeminiLive } from "@/hooks/useGeminiLive";
import { useCatalystZia } from "@/hooks/useCatalystZia";
import { useVAD } from "@/hooks/useVAD";
import { containsKannada, detectLanguage } from "@/lib/language-detect";
import {
  ensureAudioContextRunning,
  float32ToPcm16,
  GEMINI_LIVE_OUTPUT_SAMPLE_RATE,
  pcm16ToBlob,
  StreamingAudioPlayer,
  ZIA_SAMPLE_RATE,
} from "@/lib/audio";
import { useKspStore, type Language } from "@/lib/store";
import { cn } from "@/lib/utils";

export type VoiceState =
  | "idle"
  | "permission"
  | "listening"
  | "capturing"
  | "processing"
  | "speaking"
  | "error";

export interface VoiceRecorderProps {
  /** Disable the recorder while parent is handling a non-voice action. */
  disabled?: boolean;
  /** Override the auto-detected language. Defaults to store. */
  language?: Language;
  /** Called with the final transcript once STT settles. */
  onTranscript?: (text: string, language: Language) => void;
  /** Called when the assistant finishes speaking. */
  onResponseComplete?: (text: string) => void;
  /** Tailwind className passthrough for layout. */
  className?: string;
}

const LABEL: Record<VoiceState, { en: string; kn: string }> = {
  idle:        { en: "Tap to speak",            kn: "ಮಾತನಾಡಲು ಒತ್ತಿರಿ" },
  permission:  { en: "Requesting microphone…",  kn: "ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ಕೇಳಲಾಗುತ್ತಿದೆ…" },
  listening:   { en: "Listening…",              kn: "ಆಲಿಸುತ್ತಿದ್ದೇನೆ…" },
  capturing:   { en: "Recording…",              kn: "ರೆಕಾರ್ಡ್ ಆಗುತ್ತಿದೆ…" },
  processing:  { en: "Thinking…",               kn: "ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ…" },
  speaking:    { en: "Responding…",             kn: "ಉತ್ತರಿಸುತ್ತಿದ್ದೇನೆ…" },
  error:       { en: "Microphone unavailable",  kn: "ಮೈಕ್ರೊಫೋನ್ ಲಭ್ಯವಿಲ್ಲ" },
};

/** RMS->volume meter columns. */
const METER_BARS = 18;

export function VoiceRecorder({
  disabled = false,
  language: languageProp,
  onTranscript,
  onResponseComplete,
  className,
}: VoiceRecorderProps): JSX.Element {
  const storeLanguage = useKspStore((s) => s.language);
  const language: Language = languageProp ?? storeLanguage;

  const [state, setState] = useState<VoiceState>("idle");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [responseText, setResponseText] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Refs for state that must not trigger re-render in hot paths.
  const isStreamingToGeminiRef = useRef(false);
  const streamingPlayerRef = useRef<StreamingAudioPlayer | null>(null);
  const utteranceLanguageRef = useRef<Language>(language);
  const aggregatedTextRef = useRef("");

  const gemini = useGeminiLive();
  const zia = useCatalystZia();

  // ─── VAD ────────────────────────────────────────────────────────────────
  const vad = useVAD({
    silenceMs: 200,
    onSpeechStart: () => {
      // Barge-in: if the assistant is mid-response, kill its audio so the
      // user can talk over it.
      if (state === "speaking") {
        stopAssistantPlayback();
      }
      setState("capturing");
      // For Kannada path, we start streaming chunks to Gemini Live immediately.
      if (language === "kn") {
        isStreamingToGeminiRef.current = true;
      }
      setInterimTranscript("");
    },
    onFrame: (frame, isSpeech) => {
      if (
        isSpeech &&
        isStreamingToGeminiRef.current &&
        gemini.state === "open"
      ) {
        gemini.sendAudio(frame);
      }
    },
    onSpeechEnd: (audio) => {
      isStreamingToGeminiRef.current = false;
      setState("processing");
      void handleUtterance(audio);
    },
    onError: (err) => {
      setState("error");
      setErrorMsg(err.message);
    },
  });

  const isMicDenied = vad.permission === "denied";

  // ─── Assistant playback (Gemini Live audio stream) ──────────────────────

  const stopAssistantPlayback = useCallback(() => {
    if (streamingPlayerRef.current) {
      streamingPlayerRef.current.stop();
      streamingPlayerRef.current = null;
    }
    zia.stopSpeaking();
  }, [zia]);

  // Wire Gemini Live audio + text events once.
  useEffect(() => {
    const offText = gemini.onTextChunk((chunk) => {
      aggregatedTextRef.current += chunk;
      setResponseText(aggregatedTextRef.current);
    });
    const offAudio = gemini.onAudioChunk((chunk) => {
      if (!streamingPlayerRef.current) {
        streamingPlayerRef.current = new StreamingAudioPlayer(
          GEMINI_LIVE_OUTPUT_SAMPLE_RATE,
        );
        streamingPlayerRef.current.onEnded(() => {
          setState((cur) => (cur === "speaking" ? "listening" : cur));
          onResponseComplete?.(aggregatedTextRef.current);
        });
        setState("speaking");
      }
      streamingPlayerRef.current.enqueuePcm16(chunk);
    });
    const offTranscript = gemini.onTranscript((text, isFinal) => {
      setInterimTranscript(text);
      if (isFinal) {
        onTranscript?.(text, utteranceLanguageRef.current);
      }
    });
    const offTurn = gemini.onTurnComplete(() => {
      // If no audio was buffered (pure text turn), advance immediately.
      if (!streamingPlayerRef.current) {
        setState((cur) => (cur === "processing" ? "listening" : cur));
        onResponseComplete?.(aggregatedTextRef.current);
      }
    });
    return () => {
      offText();
      offAudio();
      offTranscript();
      offTurn();
    };
  }, [gemini, onResponseComplete, onTranscript]);

  // ─── Utterance dispatch (post-VAD) ──────────────────────────────────────

  const handleUtterance = useCallback(
    async (audio: Float32Array) => {
      try {
        // The interim transcript (if any) tells us actual user language —
        // it may not match the toggle (code-mixed input). Default to toggle.
        const detected =
          interimTranscript && containsKannada(interimTranscript)
            ? "kn"
            : interimTranscript
            ? detectLanguage(interimTranscript) === "kn"
              ? "kn"
              : "en"
            : language;
        utteranceLanguageRef.current = detected as Language;
        aggregatedTextRef.current = "";
        setResponseText("");

        if (detected === "kn") {
          // Gemini Live path — audio was already streamed during capture.
          // We just need to ensure the session is open and signal end-of-turn.
          if (gemini.state !== "open") {
            await gemini.connect("kn");
          }
          // Final flush in case the last VAD chunk wasn't sent in onFrame
          gemini.sendAudio(audio);
          // Gemini Live treats VAD as turn boundary automatically.
        } else {
          // Catalyst Zia path — single STT request, then TTS.
          const pcm = float32ToPcm16(audio);
          const wav = pcm16ToBlob(pcm, ZIA_SAMPLE_RATE, 1);
          const stt = await zia.transcribe(wav, detected === "hi" ? "hi" : "en");
          setInterimTranscript(stt.transcript);
          onTranscript?.(stt.transcript, detected as Language);
          // Hand off to the parent — they'll resolve the LLM answer and call
          // back with text to speak. For now we echo via TTS so the loop
          // is exercisable in isolation.
          const ttsText = stt.transcript;
          aggregatedTextRef.current = ttsText;
          setResponseText(ttsText);
          setState("speaking");
          await zia.speak(ttsText, detected === "hi" ? "hi" : "en");
          onResponseComplete?.(ttsText);
          setState("listening");
        }
      } catch (err) {
        setState("error");
        setErrorMsg(err instanceof Error ? err.message : String(err));
      }
    },
    [gemini, interimTranscript, language, onResponseComplete, onTranscript, zia],
  );

  // ─── Start / stop ───────────────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    if (disabled || isMicDenied) return;
    setErrorMsg(null);
    setState("permission");
    try {
      await ensureAudioContextRunning();
      // Pre-open Gemini Live for Kannada — saves ~400ms first-audio.
      if (language === "kn" && gemini.state === "idle") {
        await gemini.connect("kn");
      }
      await vad.start();
      setState("listening");
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  }, [disabled, gemini, isMicDenied, language, vad]);

  const handleStop = useCallback(async () => {
    isStreamingToGeminiRef.current = false;
    stopAssistantPlayback();
    await vad.stop();
    setState("idle");
  }, [stopAssistantPlayback, vad]);

  // Keyboard shortcut: Space/Enter toggles when focused; Esc cancels.
  const buttonRef = useRef<HTMLButtonElement>(null);
  const handleKey = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        if (state === "idle") void handleStart();
        else void handleStop();
      } else if (e.key === "Escape") {
        void handleStop();
      }
    },
    [handleStart, handleStop, state],
  );

  // Tear down on unmount.
  useEffect(() => {
    return () => {
      stopAssistantPlayback();
      void vad.stop();
      void gemini.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Render ─────────────────────────────────────────────────────────────

  const isActive = state !== "idle" && state !== "error";
  const label = LABEL[state][language === "kn" ? "kn" : "en"];

  const bars = useMemo(() => Array.from({ length: METER_BARS }), []);
  const volume = vad.volume; // 0..~0.5 in practice

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 select-none",
        className,
      )}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-pressed={isActive}
        aria-label={label}
        aria-busy={state === "processing"}
        disabled={disabled || isMicDenied}
        onClick={isActive ? handleStop : handleStart}
        onKeyDown={handleKey}
        className={cn(
          "relative flex h-20 w-20 items-center justify-center rounded-full",
          "transition-all duration-200 outline-none",
          "focus-visible:ring-4 focus-visible:ring-amber-300/60",
          "disabled:cursor-not-allowed disabled:opacity-50",
          state === "idle" && "bg-slate-800 text-amber-100 hover:bg-slate-700",
          state === "permission" &&
            "bg-amber-500 text-slate-900 animate-pulse",
          (state === "listening" || state === "capturing") &&
            "bg-red-500 text-white shadow-[0_0_0_8px_rgba(239,68,68,0.18)]",
          state === "processing" && "bg-sky-500 text-white",
          state === "speaking" &&
            "bg-emerald-500 text-white shadow-[0_0_0_8px_rgba(16,185,129,0.18)]",
          state === "error" && "bg-rose-700 text-white",
        )}
      >
        {state === "processing" ? (
          <Loader2 className="h-9 w-9 animate-spin" aria-hidden />
        ) : state === "speaking" ? (
          <Volume2 className="h-9 w-9" aria-hidden />
        ) : isMicDenied || state === "error" ? (
          <MicOff className="h-9 w-9" aria-hidden />
        ) : (
          <Mic
            className={cn(
              "h-9 w-9",
              (state === "listening" || state === "capturing") &&
                "animate-pulse",
            )}
            aria-hidden
          />
        )}
        {/* breathing ring while listening — pure CSS, GPU-cheap */}
        {(state === "listening" || state === "capturing") && (
          <span
            aria-hidden
            className="absolute inset-0 rounded-full border-4 border-red-400/50 animate-ping"
          />
        )}
      </button>

      {/* Volume meter — 18 bars, RMS-driven. Hidden when idle. */}
      <div
        aria-hidden
        className={cn(
          "flex h-7 items-end gap-[3px] transition-opacity",
          state === "capturing" || state === "listening"
            ? "opacity-100"
            : "opacity-20",
        )}
      >
        {bars.map((_, i) => {
          // Bar height tapers from center outwards for a nice meter look.
          const center = (METER_BARS - 1) / 2;
          const distance = Math.abs(i - center) / center;
          const responsiveness = 1 - distance * 0.7;
          const norm = Math.min(1, volume * 12 * responsiveness);
          const h = 6 + Math.round(norm * 22);
          return (
            <span
              key={i}
              style={{ height: `${h}px` }}
              className={cn(
                "w-[3px] rounded-sm transition-[height] duration-75",
                state === "capturing" ? "bg-red-400" : "bg-amber-300/70",
              )}
            />
          );
        })}
      </div>

      {/* Live status text — announced to AT via aria-live. */}
      <p
        role="status"
        aria-live="polite"
        className="text-xs font-medium text-slate-400 tracking-wide"
      >
        {label}
      </p>

      {interimTranscript && (
        <p
          lang={utteranceLanguageRef.current}
          className="max-w-xs text-center text-sm text-slate-200 italic"
        >
          &ldquo;{interimTranscript}&rdquo;
        </p>
      )}

      {responseText && state === "speaking" && (
        <p
          lang={utteranceLanguageRef.current}
          className="max-w-md text-center text-sm text-emerald-200"
        >
          {responseText}
        </p>
      )}

      {(isMicDenied || state === "error") && (
        <div
          role="alert"
          className="mt-1 max-w-xs rounded-md border border-rose-700/50 bg-rose-950/40 px-3 py-2 text-center text-xs text-rose-200"
        >
          {isMicDenied
            ? language === "kn"
              ? "ಬ್ರೌಸರ್ ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನೀಡಲಾಗಿಲ್ಲ. ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಸಕ್ರಿಯಗೊಳಿಸಿ."
              : "Microphone permission was denied. Enable it in your browser site settings, then reload."
            : errorMsg ?? "Something went wrong with the voice pipeline."}
        </div>
      )}
    </div>
  );
}

export default VoiceRecorder;
