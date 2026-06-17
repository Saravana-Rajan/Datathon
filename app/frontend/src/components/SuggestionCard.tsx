"use client";

import * as React from "react";
import {
  Car,
  TrendingUp,
  Share2,
  MapPin,
  Search,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * SuggestionCard — replaces the bland inline chips in the empty state.
 *
 * Each card is a 2-line CTA with an icon, an English title, and a Kannada
 * gloss. Hover lifts the card 2px and pops a soft shadow. Click sends the
 * English query (the LLM resolves bilingually).
 */
export interface SuggestionCardProps {
  icon: LucideIcon;
  title: string;
  /** Kannada translation/gloss shown smaller beneath the title. */
  titleKn?: string;
  /** Prompt sent when the card is tapped. */
  prompt: string;
  disabled?: boolean;
  onClick: (prompt: string) => void;
  /** Accent hue (Tailwind class fragment). Defaults to "primary". */
  accent?: "primary" | "khaki" | "navy" | "rose" | "emerald" | "violet";
}

const ACCENT_BG: Record<NonNullable<SuggestionCardProps["accent"]>, string> = {
  primary: "from-sky-500/10 to-sky-500/0 text-sky-600 dark:text-sky-300",
  khaki:
    "from-amber-500/10 to-amber-500/0 text-amber-700 dark:text-amber-300",
  navy: "from-indigo-600/10 to-indigo-600/0 text-indigo-600 dark:text-indigo-300",
  rose: "from-rose-500/10 to-rose-500/0 text-rose-600 dark:text-rose-300",
  emerald:
    "from-emerald-500/10 to-emerald-500/0 text-emerald-600 dark:text-emerald-300",
  violet:
    "from-violet-500/10 to-violet-500/0 text-violet-600 dark:text-violet-300",
};

export function SuggestionCard({
  icon: Icon,
  title,
  titleKn,
  prompt,
  disabled = false,
  onClick,
  accent = "primary",
}: SuggestionCardProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onClick(prompt)}
      disabled={disabled}
      className={cn(
        "suggestion-card group relative flex flex-col gap-2 overflow-hidden rounded-2xl border border-border/60 bg-card p-3.5 text-left transition-all duration-200",
        "hover:-translate-y-0.5 hover:border-border hover:shadow-lg",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      {/* Gradient wash on hover */}
      <div
        className={cn(
          "pointer-events-none absolute inset-0 bg-gradient-to-br opacity-0 transition-opacity duration-300 group-hover:opacity-100",
          ACCENT_BG[accent],
        )}
        aria-hidden="true"
      />

      <div className="relative flex items-start gap-2.5">
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-muted/60 transition-colors group-hover:bg-white/40 dark:group-hover:bg-white/5",
            ACCENT_BG[accent].split(" ").slice(-2).join(" "),
          )}
          aria-hidden="true"
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium leading-tight tracking-tight text-foreground">
            {title}
          </span>
          {titleKn && (
            <span
              className="mt-0.5 truncate text-xs leading-snug text-muted-foreground"
              style={{
                fontFamily:
                  '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, serif',
              }}
            >
              {titleKn}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

/**
 * Default suggestion deck used by the chat empty state. The prompts are
 * intentionally English-only so the orchestrator's NER/keyword router can
 * pick them up consistently; the bilingual surface comes from titleKn.
 */
export const DEFAULT_SUGGESTIONS: Array<
  Omit<SuggestionCardProps, "onClick" | "disabled">
> = [
  {
    icon: Car,
    title: "Vehicle thefts near MG Road",
    titleKn: "ಎಂಜಿ ರಸ್ತೆ ಹತ್ತಿರ ವಾಹನ ಕಳ್ಳತನ",
    prompt: "Show vehicle theft patterns near MG Road this month",
    accent: "rose",
  },
  {
    icon: TrendingUp,
    title: "Predict tomorrow's hotspots",
    titleKn: "ನಾಳೆಯ ಹಾಟ್‌ಸ್ಪಾಟ್‌",
    prompt: "Predict next 24 hours hotspots across Bengaluru",
    accent: "khaki",
  },
  {
    icon: Share2,
    title: "Network around Ravi Kumar",
    titleKn: "ರವಿ ಕುಮಾರ್ ಜಾಲ",
    prompt: "Build the co-accused network for Ravi Kumar",
    accent: "violet",
  },
  {
    icon: MapPin,
    title: "Repeat offenders in Indiranagar",
    titleKn: "ಇಂದಿರಾನಗರ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು",
    prompt: "List repeat offenders in Indiranagar beat last 90 days",
    accent: "navy",
  },
  {
    icon: Search,
    title: "Chain snatching trends",
    titleKn: "ಚೈನ್ ಕಳ್ಳತನ ಪ್ರವೃತ್ತಿ",
    prompt: "Chain snatching trends across Bengaluru — last 30 days",
    accent: "emerald",
  },
  {
    icon: Clock,
    title: "MO match — last 30 days",
    titleKn: "ಕಾರ್ಯವಿಧಾನ ಹೊಂದಾಣಿಕೆ",
    prompt: "Find MO matches across burglaries in the last 30 days",
    accent: "primary",
  },
];

export default SuggestionCard;
