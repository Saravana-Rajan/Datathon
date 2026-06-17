"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * VoiceOrb — the centerpiece of the voice mode overlay.
 *
 * A large gradient sphere that pulses based on the current voice phase:
 *   - idle:      gentle breathing (3s scale 1.0 → 1.05)
 *   - listening: brisk pulse with blue glow (1.2s scale 1.0 → 1.15)
 *   - speaking:  irregular gold pulse, larger amplitude
 *   - thinking:  slow rotational shimmer
 *   - error:     muted, no animation
 *
 * Built entirely in CSS — no canvas/SVG shader — so it composites cheaply
 * and works inside <Suspense> without hydration mismatch. Layered:
 *   1. Outer halo (blurred radial gradient, animates opacity)
 *   2. Mid ring (conic gradient that slowly rotates)
 *   3. Core orb (radial gradient navy → khaki, animates scale)
 *   4. Highlight (top-left specular hint, fixed)
 *
 * Three floating particles orbit the core when active. They use staggered
 * animation-delay so they don't all peak together — gives organic motion.
 */
export type OrbPhase =
  | "idle"
  | "listening"
  | "speaking"
  | "thinking"
  | "error";

export interface VoiceOrbProps {
  phase?: OrbPhase;
  /** 0..1 — currently unused but reserved for VAD-driven scale. */
  level?: number;
  /** Diameter in px. Defaults to 220. */
  size?: number;
  className?: string;
}

export function VoiceOrb({
  phase = "idle",
  size = 220,
  className,
}: VoiceOrbProps): JSX.Element {
  const phaseClass =
    phase === "listening"
      ? "orb-listening"
      : phase === "speaking"
        ? "orb-speaking"
        : phase === "thinking"
          ? "orb-thinking"
          : phase === "error"
            ? "orb-error"
            : "orb-idle";

  const haloColor =
    phase === "speaking"
      ? "rgba(200, 169, 100, 0.55)" // khaki
      : phase === "listening"
        ? "rgba(96, 165, 250, 0.55)" // sky-400
        : phase === "error"
          ? "rgba(248, 113, 113, 0.35)" // red-400
          : "rgba(124, 154, 232, 0.4)";

  return (
    <div
      className={cn("relative", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {/* Outer halo */}
      <div
        className={cn("absolute inset-0 rounded-full blur-3xl", phaseClass)}
        style={{
          background: `radial-gradient(circle at center, ${haloColor} 0%, transparent 70%)`,
        }}
      />

      {/* Mid rotating ring */}
      <div
        className="absolute inset-2 rounded-full opacity-50 orb-ring"
        style={{
          background:
            "conic-gradient(from 0deg, transparent 0deg, rgba(200,169,100,0.35) 60deg, transparent 140deg, rgba(96,165,250,0.35) 220deg, transparent 300deg)",
          filter: "blur(6px)",
        }}
      />

      {/* Core orb */}
      <div
        className={cn(
          "absolute inset-4 rounded-full shadow-2xl orb-core",
          phaseClass,
        )}
        style={{
          background:
            phase === "speaking"
              ? "radial-gradient(circle at 35% 30%, #f4d68a 0%, #C8A964 35%, #6b4e1a 70%, #1a1208 100%)"
              : phase === "listening"
                ? "radial-gradient(circle at 35% 30%, #93c5fd 0%, #3b82f6 35%, #1e3a8a 70%, #0c1a3d 100%)"
                : phase === "error"
                  ? "radial-gradient(circle at 35% 30%, #fca5a5 0%, #ef4444 35%, #7f1d1d 70%, #2a0a0a 100%)"
                  : "radial-gradient(circle at 35% 30%, #6b7fb8 0%, #2a3f7a 35%, #0c1a3d 70%, #050a1f 100%)",
          boxShadow:
            phase === "speaking"
              ? "0 0 80px rgba(200,169,100,0.6), inset 0 0 40px rgba(255,220,150,0.2)"
              : phase === "listening"
                ? "0 0 80px rgba(96,165,250,0.6), inset 0 0 40px rgba(150,200,255,0.2)"
                : "0 0 50px rgba(40,60,120,0.4), inset 0 0 30px rgba(100,130,200,0.15)",
        }}
      />

      {/* Specular highlight */}
      <div
        className="absolute rounded-full opacity-60"
        style={{
          top: "18%",
          left: "22%",
          width: "30%",
          height: "20%",
          background:
            "radial-gradient(ellipse at center, rgba(255,255,255,0.7) 0%, transparent 70%)",
          filter: "blur(4px)",
        }}
      />

      {/* Floating particles (active phases only) */}
      {(phase === "listening" || phase === "speaking") && (
        <>
          <span className="orb-particle orb-particle-1" />
          <span className="orb-particle orb-particle-2" />
          <span className="orb-particle orb-particle-3" />
        </>
      )}
    </div>
  );
}

export default VoiceOrb;
