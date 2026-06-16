"use client";

import * as React from "react";
import { Send, Mic, MicOff, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useKspStore, type Language } from "@/lib/store";

/**
 * Suggested-question chips. Three per language seed the conversation for
 * first-time users so judges and field officers immediately see what KSP
 * Saathi can do. The Kannada chips intentionally exercise transliteration
 * (named entity) + temporal reasoning + map-grounded queries.
 */
const SUGGESTIONS: Record<Language, string[]> = {
  en: [
    "Show patterns near MG Road",
    "Predict next week's hotspots",
    "Repeat offenders in Indiranagar",
  ],
  kn: [
    "ಎಂಜಿ ರಸ್ತೆಯ ಬಳಿ ಮಾದರಿಗಳನ್ನು ತೋರಿಸಿ",
    "ಮುಂದಿನ ವಾರದ ಮುನ್ಸೂಚನೆ",
    "ರವಿ ಕುಮಾರ್ ಮಾಹಿತಿ",
  ],
};

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
  /** Hide the suggestions row once the conversation is underway. */
  showSuggestions?: boolean;
  className?: string;
}

/**
 * Bottom input row for the chat panel.
 *
 * Layout: [suggestion chips above] [text input | mic | send].
 *
 * IME-friendly: we don't intercept Enter while the IME composition is active,
 * so Kannada / Devanagari / Korean / Chinese / Japanese candidate windows
 * work normally. Press Enter (without Shift) commits the message; Shift+Enter
 * is reserved for a future textarea upgrade.
 */
export function MessageInput({
  value,
  onChange,
  onSubmit,
  isLoading,
  onSendText,
  onToggleVoice,
  isRecording = false,
  showSuggestions = true,
  className,
}: MessageInputProps): JSX.Element {
  const language = useKspStore((s) => s.language);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const composingRef = React.useRef(false);

  // Refocus the input after a suggestion is sent so the officer can chain
  // follow-ups without reaching for the mouse.
  const handleSuggestion = React.useCallback(
    (text: string) => {
      onSendText(text);
      inputRef.current?.focus();
    },
    [onSendText],
  );

  const placeholder =
    language === "kn"
      ? "ಪ್ರಶ್ನೆ ಕೇಳಿ... (ಕನ್ನಡ / English ಎರಡೂ)"
      : "Ask a question... (English or ಕನ್ನಡ)";

  const suggestions = SUGGESTIONS[language] ?? SUGGESTIONS.en;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {showSuggestions && (
        <div
          role="group"
          aria-label="Suggested questions"
          className="flex flex-wrap gap-1.5"
        >
          <span
            className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground"
            aria-hidden="true"
          >
            <Sparkles className="h-3 w-3" />
            Try
          </span>
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => handleSuggestion(s)}
              disabled={isLoading}
              className="rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              style={
                /[ಀ-೿]/.test(s)
                  ? {
                      fontFamily:
                        '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, sans-serif',
                    }
                  : undefined
              }
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="flex items-end gap-2"
        aria-label="Send a message"
      >
        <label htmlFor="ksp-chat-input" className="sr-only">
          Message Saathi
        </label>
        <Input
          ref={inputRef}
          id="ksp-chat-input"
          autoComplete="off"
          autoCorrect="off"
          // lang/dir hints help the OS IME pick the right keyboard for Kannada
          // users on mobile + improve screen-reader pronunciation.
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
              // Allow IME to commit; don't submit yet.
              e.stopPropagation();
            }
          }}
          disabled={isLoading}
          className="flex-1"
          aria-busy={isLoading}
          style={
            /[ಀ-೿]/.test(value)
              ? {
                  fontFamily:
                    '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, sans-serif',
                }
              : undefined
          }
        />

        <Button
          type="button"
          variant={isRecording ? "destructive" : "ghost"}
          size="icon"
          onClick={onToggleVoice}
          disabled={isLoading && !isRecording}
          aria-label={isRecording ? "Stop recording" : "Start voice input"}
          aria-pressed={isRecording}
        >
          {isRecording ? (
            <MicOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Mic className="h-4 w-4" aria-hidden="true" />
          )}
        </Button>

        <Button
          type="submit"
          size="icon"
          disabled={isLoading || value.trim().length === 0}
          aria-label="Send message"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </Button>
      </form>
    </div>
  );
}

export default MessageInput;
