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
      ? "ಪ್ರಶ್ನೆ ಕೇಳಿ... ಅಥವಾ ಮೈಕ್ ಒತ್ತಿ ಮಾತನಾಡಿ"
      : "Ask anything... or tap the mic to speak";

  const isKannada = /[ಀ-೿]/.test(value);

  return (
    <form
      onSubmit={onSubmit}
      className={cn(
        "flex items-center gap-2 rounded-2xl border border-border/70 bg-card/95 p-1.5 shadow-sm backdrop-blur transition-all focus-within:border-primary/50 focus-within:shadow-md",
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

      {/* Sophisticated mic button — gradient, glow, larger tap target */}
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
          "relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white transition-all duration-200",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          isRecording
            ? "mic-button-active bg-gradient-to-br from-red-500 to-red-700 shadow-lg"
            : "bg-gradient-to-br from-[#1a2a5c] via-[#0c1a3d] to-[#050a1f] shadow-md hover:scale-[1.04] hover:shadow-xl hover:from-[#243882] hover:to-[#0c1a3d]",
        )}
      >
        {isRecording ? (
          <>
            <MicOff className="relative h-4 w-4" aria-hidden="true" />
            <span className="absolute -right-0.5 -top-0.5 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
          </>
        ) : (
          <>
            <Mic className="h-4 w-4" aria-hidden="true" />
            {/* Sound-wave hint emoji-free */}
            <AudioLines
              className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 text-[#C8A964] opacity-80"
              aria-hidden="true"
            />
          </>
        )}
      </button>

      <Button
        type="submit"
        size="icon"
        disabled={isLoading || value.trim().length === 0}
        aria-label="Send message"
        className={cn(
          "h-11 w-11 shrink-0 rounded-xl transition-transform",
          "hover:scale-[1.04] active:scale-95",
          "bg-gradient-to-br from-primary to-blue-700 shadow-md",
        )}
      >
        <Send className="h-4 w-4" aria-hidden="true" />
      </Button>
    </form>
  );
}

export default MessageInput;
