"use client";

import * as React from "react";
import { Send, Mic, MicOff, AudioLines } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useKspStore } from "@/lib/store";

export interface MessageInputProps {
  /** Bound to `useChat().input`. */
  value: string;
  /** Bound to `useChat().handleInputChange`. */
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** Bound to `useChat().handleSubmit`. */
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  /** True while a response is generating. Disables Send. */
  isLoading: boolean;
  /** Programmatic submit (used by suggestion chips). */
  onSendText: (text: string) => void;
  /** Toggle the voice recorder modal/inline UI. */
  onToggleVoice?: () => void;
  /** Whether the voice recorder is currently capturing audio. */
  isRecording?: boolean;
  /** Hide the suggestions row once the conversation is underway. Kept for
   *  backwards-compat with ChatPanel — empty state is now handled by the
   *  parent surface (SuggestionCard grid). */
  showSuggestions?: boolean;
  className?: string;
}

/**
 * Bottom input row for the chat panel.
 *
 * Premium voice product layout: rounded pill with [text input | mic | send].
 * The mic is the most prominent affordance — it's a square 44×44 rounded-xl
 * gradient button that pulses when active and tips the user into the
 * full-screen Voice Mode overlay.
 *
 * IME-friendly: we don't intercept Enter while the IME composition is active.
 */
export function MessageInput({
  value,
  onChange,
  onSubmit,
  isLoading,
  onSendText: _onSendText,
  onToggleVoice,
  isRecording = false,
  showSuggestions: _showSuggestions = true,
  className,
}: MessageInputProps): JSX.Element {
  const language = useKspStore((s) => s.language);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const composingRef = React.useRef(false);

  const placeholder =
    language === "kn"
      ? "ಪ್ರಶ್ನೆ ಕೇಳಿ... English ಅಥವಾ ಕನ್ನಡ"
      : "Ask anything... English or ಕನ್ನಡ";

  const isKannada = /[ಀ-೿]/.test(value);

  return (
    <form
      onSubmit={onSubmit}
      className={cn(
        "flex items-center gap-2 rounded-full border border-slate-200/80 bg-white p-1.5 pl-5 shadow-[0_2px_18px_-4px_rgba(124,92,250,0.10)] transition-all focus-within:border-[#7c5cfa]/40 focus-within:shadow-[0_4px_24px_-2px_rgba(124,92,250,0.18)] dark:border-white/10 dark:bg-white/5",
        className,
      )}
      aria-label="Send a message"
    >
      <label htmlFor="ksp-chat-input" className="sr-only">
        Message Sarvik
      </label>

      <Input
        ref={inputRef}
        id="ksp-chat-input"
        autoComplete="off"
        autoCorrect="off"
        lang={language === "kn" ? "kn-IN" : "en-IN"}
        dir="auto"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onCompositionStart={() => {
          composingRef.current = true;
        }}
        onCompositionEnd={() => {
          composingRef.current = false;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && composingRef.current) {
            e.stopPropagation();
          }
        }}
        disabled={isLoading}
        className="flex-1 border-0 bg-transparent text-[15px] shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
        aria-busy={isLoading}
        style={
          isKannada
            ? {
                fontFamily:
                  '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, sans-serif',
              }
            : { letterSpacing: "-0.005em" }
        }
      />

      {/* Mic — small gray circle */}
      <button
        type="button"
        onClick={onToggleVoice}
        disabled={isLoading && !isRecording}
        aria-label={
          isRecording
            ? language === "kn"
              ? "ಧ್ವನಿ ನಿಲ್ಲಿಸಿ"
              : "Stop voice mode"
            : language === "kn"
              ? "ಧ್ವನಿ ಮೋಡ್ ತೆರೆಯಿರಿ"
              : "Open voice mode"
        }
        aria-pressed={isRecording}
        className={cn(
          "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200",
          "focus:outline-none focus:ring-2 focus:ring-[#7c5cfa] focus:ring-offset-1",
          "disabled:cursor-not-allowed disabled:opacity-50",
          isRecording
            ? "mic-button-active bg-gradient-to-br from-rose-500 to-rose-600 text-white shadow-md"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/15",
        )}
      >
        {isRecording ? (
          <>
            <MicOff className="relative h-3.5 w-3.5" aria-hidden="true" />
            <span className="absolute -right-0.5 -top-0.5 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
          </>
        ) : (
          <Mic className="h-3.5 w-3.5" aria-hidden="true" />
        )}
      </button>

      {/* Live waveform — sits next to the mic; signals always-on listening */}
      <button
        type="button"
        onClick={onToggleVoice}
        disabled={isLoading}
        aria-label={
          language === "kn"
            ? "ಲೈವ್ ಧ್ವನಿ ಮೋಡ್ ಆನ್/ಆಫ್"
            : "Toggle live voice mode"
        }
        className={cn(
          "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-slate-500 transition-all duration-200",
          "hover:bg-slate-100 hover:text-[#7c5cfa] dark:text-slate-400 dark:hover:bg-white/10",
          "focus:outline-none focus:ring-2 focus:ring-[#7c5cfa] focus:ring-offset-1",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        <AudioLines className="h-4 w-4" aria-hidden="true" />
      </button>

      <Button
        type="submit"
        size="icon"
        disabled={isLoading || value.trim().length === 0}
        aria-label="Send message"
        className={cn(
          "h-9 w-9 shrink-0 rounded-full transition-all",
          "hover:scale-[1.05] active:scale-95",
          "border-0 text-white shadow-md hover:shadow-lg",
        )}
        style={{
          background:
            "linear-gradient(135deg, #7c5cfa 0%, #4f46e5 50%, #ec4899 100%)",
          boxShadow: "0 4px 14px rgba(124, 92, 250, 0.35)",
        }}
      >
        <Send className="h-3.5 w-3.5" aria-hidden="true" />
      </Button>
    </form>
  );
}

export default MessageInput;
