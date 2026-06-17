"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SparkOrb — the signature atmospheric orb of the SparkFinch / Sarvik aesthetic.
 *
 * Image-backed implementation: a hi-res `voice-orb.png` rendered inside an
 * animated container. The PNG is the visual; the wrapper drives the
 * breath/listening/speaking/thinking animations via the existing
 * `.spark-core.spark-*` CSS keyframes in `globals.css` (no new CSS shipped).
 *
 * Phases mirror VoiceOrb (idle | listening | speaking | thinking | error).
 *
 * Sizes (recommended via the `size` prop):
 *   - sm  ≈ 80px  → inline / mic-button decoration
 *   - md  ≈ 200px → chat empty state
 *   - lg  ≈ 320px → voice-mode hero
 */
export type SparkOrbPhase =
  | "idle"
  | "listening"
  | "speaking"
  | "thinking"
  | "error";

export interface SparkOrbProps {
  phase?: SparkOrbPhase;
  /** Diameter in px. Defaults to 200. Use 80 / 200 / 320 for sm / md / lg. */
  size?: number;
  className?: string;
}

const ORB_SRC = "/app/voice-orb.png";

export function SparkOrb({
  phase = "idle",
  size = 200,
  className,
}: SparkOrbProps): JSX.Element {
  const phaseClass =
    phase === "listening"
      ? "spark-listening"
      : phase === "speaking"
        ? "spark-speaking"
        : phase === "thinking"
          ? "spark-thinking"
          : phase === "error"
            ? "spark-error"
            : "spark-idle";

  // Scale every absolute pixel relative to the canonical 200px design so the
  // orb composes correctly at 80px and 320px without re-tuning.
  const s = size / 200;
  const px = (n: number) => `${n * s}px`;

  return (
    <div
      className={cn("relative", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {/* Outer atmospheric halo (violet → transparent), gently pulsing */}
      <div
        className={cn("spark-halo absolute rounded-full", phaseClass)}
        style={{
          inset: px(-30),
          background:
            "radial-gradient(circle at center, rgba(167,139,250,0.55) 0%, rgba(96,165,250,0.25) 40%, transparent 70%)",
          filter: `blur(${px(28)})`,
        }}
      />

      {/* Drop-shadow glow that follows the orb silhouette */}
      <div
        className={cn("absolute inset-0 rounded-full", phaseClass)}
        style={{
          background:
            "radial-gradient(circle at 50% 55%, rgba(124,92,250,0.45) 0%, rgba(236,72,153,0.18) 45%, transparent 75%)",
          filter: `blur(${px(20)})`,
          opacity: 0.85,
        }}
      />

      {/* Core PNG orb — animated via spark-core keyframes */}
      <img
        src={ORB_SRC}
        alt=""
        draggable={false}
        className={cn(
          "spark-core absolute inset-0 h-full w-full select-none rounded-full object-contain",
          phaseClass,
        )}
        style={{
          // Subtle filter that matches the legacy CSS-orb's specular feel and
          // keeps the image from looking pasted-on against the page bg.
          filter: `drop-shadow(0 ${px(14)} ${px(36)} rgba(124,92,250,0.35))`,
          willChange: "transform, opacity",
        }}
      />
    </div>
  );
}

export default SparkOrb;
