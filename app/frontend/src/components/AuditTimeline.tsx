"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Vertical timeline scaffold for the audit drawer.
 *
 * The timeline is a flex column of children where each child renders one
 * `AuditStep`. This component owns the vertical "spine" line and the
 * spacing between dots — the dot itself is rendered by `AuditStep` so it
 * can colour-match the per-step status.
 *
 * Visual contract for children:
 *   - Each direct child must render an element with `data-audit-step`,
 *     which is what this component spaces with the gradient spine behind.
 *   - The spine is positioned absolutely behind the children at `left-4`
 *     so children should reserve at least `pl-10` of left padding for the
 *     dot + spine clearance.
 */
export interface AuditTimelineProps {
  children: React.ReactNode;
  className?: string;
}

export function AuditTimeline({
  children,
  className,
}: AuditTimelineProps): JSX.Element {
  return (
    <ol
      className={cn(
        "relative flex flex-col gap-3",
        // The spine is a thin gradient line that runs the full height of
        // the list, sitting under the dots. The mask-image trick fades the
        // top/bottom so it visually "starts" and "ends" at the first/last
        // dot rather than abruptly clipping.
        "before:pointer-events-none before:absolute before:left-4 before:top-2 before:bottom-2 before:w-px",
        "before:bg-gradient-to-b before:from-border before:via-border before:to-border/40",
        className,
      )}
      aria-label="AI reasoning timeline"
    >
      {children}
    </ol>
  );
}

export default AuditTimeline;
