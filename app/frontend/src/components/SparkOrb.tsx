"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SparkOrb — the signature gradient orb of the SparkFinch / Sarvik aesthetic.
 *
 * Pure CSS implementation: three overlapping radial-gradient blurred circles
 * (purple / pink / cyan) on top of a base sphere with a specular highlight.
 * No SVG, no canvas — composites cheaply, animates on the GPU, and ships zero
 * extra bytes beyond the (already-loaded) Tailwind/CSS pipeline.
 *
 * Phases mirror VoiceOrb (idle | listening | speaking | thinking | error)
 * but the palette stays purple/pink/cyan instead of navy/khaki.
 *
 * Sizes:
 *   - 80px  → inline / mic-button decoration
 *   - 200px → chat empty state
 *   - 320px → voice mode hero
 */
export type SparkOrbPhase =
  | "idle"
  | "listening"
  | "speaking"
  | "thinking"
  | "error";

export interface SparkOrbProps {
  phase?: SparkOrbPhase;
  /** Diameter in px. Defaults to 200. */
  size?: number;
  className?: string;
}

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
      {/* Outer atmospheric halo (purple → transparent) */}
      <div
        className={cn("spark-halo absolute rounded-full", phaseClass)}
        style={{
          inset: px(-30),
          background:
            "radial-gradient(circle at center, rgba(167,139,250,0.55) 0%, rgba(96,165,250,0.25) 40%, transparent 70%)",
          filter: `blur(${px(28)})`,
        }}
      />

      {/* Core sphere — base navy-purple base with specular */}
      <div
        className={cn("spark-core absolute inset-0 rounded-full", phaseClass)}
        style={{
          background:
            "radial-gradient(circle at 30% 25%, #f0d4ff 0%, #c5a3f5 18%, #8b5cf6 42%, #4f46e5 65%, #1e1b4b 90%, #0c0a2e 100%)",
          boxShadow: `
            0 ${px(20)} ${px(60)} rgba(124, 92, 250, 0.35),
            0 ${px(8)} ${px(28)} rgba(79, 70, 229, 0.30),
            inset 0 0 ${px(40)} rgba(255, 200, 240, 0.15)
          `,
        }}
      />

      {/* Pink blob — top-right */}
      <div
        className="spark-blob spark-blob-pink absolute rounded-full mix-blend-screen"
        style={{
          top: "5%",
          right: "5%",
          width: "60%",
          height: "55%",
          background:
            "radial-gradient(circle at center, rgba(255, 130, 200, 0.85) 0%, rgba(236, 72, 153, 0.4) 40%, transparent 75%)",
          filter: `blur(${px(18)})`,
        }}
      />

      {/* Cyan blob — bottom-left */}
      <div
        className="spark-blob spark-blob-cyan absolute rounded-full mix-blend-screen"
        style={{
          bottom: "5%",
          left: "5%",
          width: "55%",
          height: "55%",
          background:
            "radial-gradient(circle at center, rgba(125, 211, 252, 0.85) 0%, rgba(56, 189, 248, 0.45) 40%, transparent 75%)",
          filter: `blur(${px(20)})`,
        }}
      />

      {/* Purple deep blob — center-bottom */}
      <div
        className="spark-blob spark-blob-violet absolute rounded-full mix-blend-screen"
        style={{
          top: "30%",
          left: "25%",
          width: "55%",
          height: "55%",
          background:
            "radial-gradient(circle at center, rgba(196, 181, 253, 0.75) 0%, rgba(139, 92, 246, 0.4) 40%, transparent 75%)",
          filter: `blur(${px(22)})`,
        }}
      />

      {/* Specular highlight (top-left) */}
      <div
        className="absolute rounded-full opacity-70"
        style={{
          top: "14%",
          left: "20%",
          width: "30%",
          height: "20%",
          background:
            "radial-gradient(ellipse at center, rgba(255,255,255,0.85) 0%, transparent 70%)",
          filter: `blur(${px(6)})`,
        }}
      />
    </div>
  );
}

export default SparkOrb;
