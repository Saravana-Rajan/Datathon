"use client";

/**
 * DateRangeSlider — accessible dual-handle slider for time scrubbing the map.
 *
 * Uses two range inputs stacked on top of a shared track so we get keyboard
 * support, screen-reader labels, and crisp focus rings without pulling in
 * a heavyweight slider lib. Values are emitted as `[startISO, endISO]`.
 *
 * The "Play" button advances a 1-week window forward through time, giving
 * the demo a smooth animated reveal of marker visibility.
 */

import * as React from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { isoToMillis } from "@/lib/map-utils";

interface DateRangeSliderProps {
  /** Outer bounds the user can scrub between (ISO yyyy-mm-dd). */
  min: string;
  max: string;
  /** Current window [startISO, endISO]. */
  value: [string, string];
  onChange: (next: [string, string]) => void;
  /** Animation step in days when Play is pressed. */
  stepDays?: number;
  /** Animation tick in ms. */
  tickMs?: number;
  className?: string;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function toISO(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export function DateRangeSlider({
  min,
  max,
  value,
  onChange,
  stepDays = 7,
  tickMs = 600,
  className,
}: DateRangeSliderProps): React.ReactElement {
  const minMs = isoToMillis(min);
  const maxMs = isoToMillis(max);
  const startMs = clamp(isoToMillis(value[0]), minMs, maxMs);
  const endMs = clamp(isoToMillis(value[1]), startMs, maxMs);

  const [playing, setPlaying] = React.useState(false);

  // Drive the play loop with a single interval. Reset whenever bounds change.
  React.useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      const span = endMs - startMs;
      const nextStart = startMs + stepDays * DAY_MS;
      const nextEnd = nextStart + span;
      if (nextEnd > maxMs) {
        // Loop back to the beginning so the demo keeps animating.
        onChange([toISO(minMs), toISO(minMs + span)]);
      } else {
        onChange([toISO(nextStart), toISO(nextEnd)]);
      }
    }, tickMs);
    return () => window.clearInterval(id);
  }, [playing, startMs, endMs, minMs, maxMs, stepDays, tickMs, onChange]);

  // Guard against the parent flipping min/max — fail gracefully.
  if (!Number.isFinite(minMs) || !Number.isFinite(maxMs) || maxMs <= minMs) {
    return (
      <div className={className}>
        <p className="text-xs text-muted-foreground">
          No date range available.
        </p>
      </div>
    );
  }

  const total = maxMs - minMs;
  const startPct = ((startMs - minMs) / total) * 100;
  const endPct = ((endMs - minMs) / total) * 100;

  const handleStart = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const next = clamp(Number(e.target.value), minMs, endMs);
    onChange([toISO(next), toISO(endMs)]);
  };
  const handleEnd = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const next = clamp(Number(e.target.value), startMs, maxMs);
    onChange([toISO(startMs), toISO(next)]);
  };
  const reset = (): void => {
    setPlaying(false);
    onChange([min, max]);
  };

  return (
    <div
      className={
        "rounded-md border bg-background/95 p-3 shadow-sm backdrop-blur " +
        (className ?? "")
      }
      role="group"
      aria-label="Date range scrubber"
    >
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="font-mono text-muted-foreground">{toISO(startMs)}</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPlaying((p) => !p)}
            className="inline-flex h-7 w-7 items-center justify-center rounded border text-foreground hover:bg-muted"
            aria-label={playing ? "Pause time animation" : "Play time animation"}
            aria-pressed={playing}
          >
            {playing ? (
              <Pause className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            onClick={reset}
            className="inline-flex h-7 w-7 items-center justify-center rounded border text-foreground hover:bg-muted"
            aria-label="Reset date range"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
        <span className="font-mono text-muted-foreground">{toISO(endMs)}</span>
      </div>

      <div className="relative h-6">
        {/* Track */}
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded bg-muted" />
        {/* Selected range */}
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded bg-primary"
          style={{
            left: `${startPct}%`,
            width: `${Math.max(0, endPct - startPct)}%`,
          }}
        />
        {/* Inputs — both span the full track; pointer-events trick lets each
            thumb stay independently grabbable. */}
        <input
          type="range"
          min={minMs}
          max={maxMs}
          step={DAY_MS}
          value={startMs}
          onChange={handleStart}
          aria-label="Start date"
          className="pointer-events-none absolute inset-0 h-6 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:bg-background [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border [&::-moz-range-thumb]:border-primary [&::-moz-range-thumb]:bg-background"
        />
        <input
          type="range"
          min={minMs}
          max={maxMs}
          step={DAY_MS}
          value={endMs}
          onChange={handleEnd}
          aria-label="End date"
          className="pointer-events-none absolute inset-0 h-6 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:bg-background [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border [&::-moz-range-thumb]:border-primary [&::-moz-range-thumb]:bg-background"
        />
      </div>
    </div>
  );
}

export default DateRangeSlider;
