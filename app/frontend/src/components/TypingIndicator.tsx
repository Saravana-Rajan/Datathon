"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Three-dot "AI is typing" indicator shown while the assistant is generating.
 *
 * Visual: three dots bouncing in sequence using staggered Tailwind animation
 * delays. Pure CSS — no JS animation loop, runs cheaply during streaming.
 *
 * Accessibility: announced politely to screen readers so blind/low-vision
 * users know the assistant is working. Hidden from the a11y tree once the
 * caller unmounts it.
 */
export interface TypingIndicatorProps {
  /** Optional label override (e.g. localized "ಯೋಚಿಸುತ್ತಿದೆ..." for Kannada UI). */
  label?: string;
  className?: string;
}

export function TypingIndicator({
  label = "Saathi is thinking",
  className,
}: TypingIndicatorProps): JSX.Element {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-2xl rounded-bl-sm border bg-muted px-3 py-2",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
      <span
        className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.3s]"
        aria-hidden="true"
      />
      <span
        className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.15s]"
        aria-hidden="true"
      />
      <span
        className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70"
        aria-hidden="true"
      />
    </div>
  );
}

export default TypingIndicator;
