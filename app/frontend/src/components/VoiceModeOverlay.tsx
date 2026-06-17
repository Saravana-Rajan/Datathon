"use client";

import * as React from "react";
import { ChevronDown, X, Mic, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { useKspStore, type Language } from "@/lib/store";
import { SparkOrb, type SparkOrbPhase } from "./SparkOrb";
import dynamic from "next/dynamic";

type OrbPhase = SparkOrbPhase;

// Lazy-load the heavy VoiceRecorder (same reason ChatPanel does — vad-web WASM
// must not run during SSG prerender).
const VoiceRecorder = dynamic(
  () => import("./VoiceRecorder").then((m) => m.VoiceRecorder),
  { ssr: false },
);

export interface VoiceModeOverlayProps {
  open: boolean;
  onClose: () => void;
  onTranscript?: (text: string, language: Language) => void;
  onResponseComplete?: (text: string) => void;
  /** Whether Gemini Live (full bidirectional) is wired up. */
  liveAvailable: boolean;
}

/**
 * Full-screen voice mode overlay — the premium "ChatGPT voice mode" surface.
 *
 * Layout:
 *   ┌────────────────────────────────────────────────┐
 *   │  [↓ minimize]                          [✕]    │
 *   │                                                │
 *   │           [Listening in Kannada]              │
 *   │                                                │
 *   │              ╭──────────╮                     │
 *   │              │   ORB    │  (220px)            │
 *   │              ╰──────────╯                     │
 *   │                                                │
 *   │       "ಎಂಜಿ ರಸ್ತೆಯಲ್ಲಿ..."   <- subtitle      │
 *   │                                                │
 *   │              [● Tap to stop]                  │
 *   └────────────────────────────────────────────────┘
 *
 * The orb phase is driven by the VoiceRecorder's internal state machine via
 * a window CustomEvent (`ksp:voice-state`). We listen here and translate it
 * to an OrbPhase. The transcript text is also pumped through `onTranscript`
 * + a local mirror so we can show live subtitles below the orb.
 */
export function VoiceModeOverlay({
  open,
  onClose,
  onTranscript,
  onResponseComplete,
  liveAvailable,
}: VoiceModeOverlayProps): JSX.Element | null {
  const language = useKspStore((s) => s.language);
  const [phase, setPhase] = React.useState<OrbPhase>("idle");
  const [subtitle, setSubtitle] = React.useState<string>("");
  const [subtitleLang, setSubtitleLang] = React.useState<Language>(language);

  // Reset on open/close.
  React.useEffect(() => {
    if (open) {
      setPhase("listening");
      setSubtitle("");
    } else {
      setPhase("idle");
    }
  }, [open]);

  // Listen for voice state events emitted by VoiceRecorder (we don't wire
  // through props because VoiceRecorder is lazy-loaded and has its own
  // internal state machine).
  React.useEffect(() => {
    if (!open) return;
    function onStateChange(e: Event) {
      const detail = (e as CustomEvent<{ state: string }>).detail;
      const s = detail?.state;
      if (!s) return;
      if (s === "listening") setPhase("listening");
      else if (s === "capturing") setPhase("listening");
      else if (s === "processing") setPhase("thinking");
      else if (s === "speaking") setPhase("speaking");
      else if (s === "error") setPhase("error");
      else if (s === "idle") setPhase("idle");
    }
    window.addEventListener("ksp:voice-state", onStateChange as EventListener);
    return () =>
      window.removeEventListener(
        "ksp:voice-state",
        onStateChange as EventListener,
      );
  }, [open]);

  // Esc to close.
  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const handleTranscript = React.useCallback(
    (text: string, lang: Language) => {
      setSubtitle(text);
      setSubtitleLang(lang);
      onTranscript?.(text, lang);
    },
    [onTranscript],
  );

  const handleResponseComplete = React.useCallback(
    (text: string) => {
      setSubtitle(text);
      onResponseComplete?.(text);
      // Drop phase back to listening after AI finishes speaking.
      setPhase("listening");
    },
    [onResponseComplete],
  );

  if (!open) return null;

  const statusLabel = (() => {
    if (phase === "speaking") {
      return language === "kn" ? "ಸಾರ್ವಿಕ್ ಮಾತನಾಡುತ್ತಿದೆ" : "Sarvik is speaking";
    }
    if (phase === "thinking") {
      return language === "kn" ? "ಯೋಚಿಸುತ್ತಿದೆ…" : "Thinking…";
    }
    if (phase === "error") {
      return language === "kn" ? "ದೋಷ" : "Error";
    }
    return language === "kn"
      ? "ಕನ್ನಡದಲ್ಲಿ ಆಲಿಸುತ್ತಿದ್ದೇನೆ"
      : "Listening in English";
  })();

  const helperLabel =
    language === "kn"
      ? "ಮಾತನಾಡಿ — ಮುಗಿದಾಗ ತಾನಾಗಿ ಪ್ರತಿಕ್ರಿಯಿಸುತ್ತದೆ"
      : "Just speak — Sarvik responds when you pause";

  const subtitleIsKannada = /[ಀ-೿]/.test(subtitle);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Voice conversation mode"
      className="fixed inset-0 z-50 flex flex-col voice-overlay"
    >
      {/* Backdrop with blur */}
      <div className="absolute inset-0 voice-overlay-backdrop" />

      {/* Foreground content */}
      <div className="relative z-10 flex flex-1 flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-3 py-1.5 text-xs font-medium uppercase tracking-wider text-slate-600 backdrop-blur transition-colors hover:bg-white hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#7c5cfa]/30"
            aria-label="Minimize voice mode"
          >
            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            {language === "kn" ? "ಚಿಕ್ಕದು" : "Minimize"}
          </button>

          <div
            className="rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7c5cfa] backdrop-blur"
            aria-live="polite"
          >
            {liveAvailable ? "Gemini Live" : "Dictation"}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-200 bg-white/70 p-2 text-slate-600 backdrop-blur transition-colors hover:bg-white hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#7c5cfa]/30"
            aria-label="Close voice mode"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Center stack: status, orb, subtitle */}
        <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
          <p
            className="mb-8 text-[11px] font-semibold uppercase tracking-[0.4em] text-slate-500"
            style={
              /[ಀ-೿]/.test(statusLabel)
                ? {
                    fontFamily:
                      '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, sans-serif',
                    letterSpacing: "0.2em",
                  }
                : undefined
            }
          >
            {statusLabel}
          </p>

          <SparkOrb phase={phase} size={320} />

          <div className="mt-12 min-h-[5rem] max-w-2xl">
            {subtitle ? (
              <p
                className="voice-subtitle text-2xl font-light leading-relaxed text-slate-800 dark:text-white/90"
                style={
                  subtitleIsKannada
                    ? {
                        fontFamily:
                          '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, serif',
                        letterSpacing: "0",
                      }
                    : { letterSpacing: "-0.01em" }
                }
              >
                {subtitle}
              </p>
            ) : (
              <p className="text-base font-light tracking-wide text-slate-500 dark:text-white/40">
                {helperLabel}
              </p>
            )}
          </div>
        </div>

        {/* Hidden VoiceRecorder mounted to drive the real audio pipeline.
            We hide the default UI by clipping it and styling it offscreen,
            but keep it interactive so VAD + Gemini Live keep working. */}
        <div className="voice-recorder-host" aria-hidden="false">
          <VoiceRecorder
            language={language}
            onTranscript={handleTranscript}
            onResponseComplete={handleResponseComplete}
          />
        </div>

        {/* Bottom action row — 3 pill controls (mic / stop / text-mode) */}
        <div className="flex justify-center pb-12 pt-4">
          <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white/70 p-2 shadow-[0_8px_30px_-8px_rgba(124,92,250,0.25)] backdrop-blur-xl dark:border-white/10 dark:bg-white/10">
            <button
              type="button"
              className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-700 transition-colors hover:bg-slate-200 dark:bg-white/10 dark:text-slate-200"
              aria-label="Mute"
            >
              <Mic className="h-5 w-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="group relative flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition-transform hover:scale-[1.05] focus:outline-none focus:ring-2 focus:ring-rose-500/40"
              style={{
                background:
                  "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
                boxShadow: "0 8px 24px rgba(239, 68, 68, 0.35)",
              }}
              aria-label="End voice conversation"
            >
              <span className="absolute inset-2 rounded-full border-2 border-white/30" />
              <span className="relative h-3 w-3 rounded-sm bg-white" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-700 transition-colors hover:bg-slate-200 dark:bg-white/10 dark:text-slate-200"
              aria-label="Switch to text mode"
            >
              <MessageSquare className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default VoiceModeOverlay;
