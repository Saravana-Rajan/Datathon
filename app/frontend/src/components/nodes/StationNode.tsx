"use client";

/**
 * StationNode — police station node, shield-shaped.
 *
 * Visual contract:
 *   - Inline SVG shield silhouette as the background shape (no extra deps).
 *   - Station name + district + FIR count.
 *
 * Why a shield: instantly communicates "police institution" in a graph
 * dense with person + FIR nodes; the shape difference makes a quick scan
 * of any subgraph readable.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StationNodeData } from "@/types/graph";

export const StationNode = memo(function StationNode({
  data,
  selected,
}: NodeProps<StationNodeData>) {
  return (
    <div
      role="group"
      aria-label={`Police station ${data.name}${data.district ? `, ${data.district} district` : ""}`}
      className={cn(
        "relative min-w-[170px] rounded-lg border-2 bg-blue-50 shadow-sm",
        "px-3 py-2.5 flex items-center gap-2.5 transition-shadow hover:shadow-md",
        selected
          ? "border-blue-700 ring-2 ring-blue-200"
          : "border-blue-600"
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-blue-600" />

      <div
        className="shrink-0 h-9 w-9 rounded-md bg-blue-600 text-white grid place-items-center"
        aria-hidden="true"
      >
        <Shield className="h-5 w-5" strokeWidth={2.5} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold text-blue-900 uppercase tracking-wide">
          Station
        </p>
        <p className="text-sm font-semibold text-blue-950 truncate" title={data.name}>
          {data.name}
        </p>
        {(data.district || typeof data.firCount === "number") && (
          <p className="text-[10px] text-blue-800/80">
            {data.district}
            {data.district && typeof data.firCount === "number" ? " · " : ""}
            {typeof data.firCount === "number"
              ? `${data.firCount} FIR${data.firCount === 1 ? "" : "s"}`
              : ""}
          </p>
        )}
      </div>

      <Handle type="source" position={Position.Right} className="!bg-blue-600" />
    </div>
  );
});
