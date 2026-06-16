"use client";

/**
 * FIRNode — case-file node.
 *
 * Visual contract (compact / "case file" shape):
 *   - Folder-tab style top border for the FIR number.
 *   - Crime type icon (drawn from a small known-crime map; falls back to a
 *     generic file icon).
 *   - Date below.
 *
 * Small footprint so several FIR nodes around one person stay readable.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import {
  FileText,
  ShieldAlert,
  Car,
  Flame,
  Skull,
  Pill,
  HandCoins,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { FIRNodeData } from "@/types/graph";

const CRIME_ICON: Record<string, React.ComponentType<{ className?: string }>> =
  {
    theft: HandCoins,
    burglary: HandCoins,
    robbery: HandCoins,
    assault: ShieldAlert,
    murder: Skull,
    homicide: Skull,
    arson: Flame,
    vehicle: Car,
    "vehicle theft": Car,
    narcotics: Pill,
    drugs: Pill,
  };

function pickIcon(crimeType: string) {
  const key = crimeType.toLowerCase();
  for (const [name, icon] of Object.entries(CRIME_ICON)) {
    if (key.includes(name)) return icon;
  }
  return FileText;
}

export const FIRNode = memo(function FIRNode({
  data,
  selected,
}: NodeProps<FIRNodeData>) {
  const Icon = pickIcon(data.crimeType);

  return (
    <div
      role="group"
      aria-label={`FIR ${data.firNo}, ${data.crimeType}, dated ${data.date}`}
      className={cn(
        "relative min-w-[150px] max-w-[180px] rounded-md border bg-amber-50",
        "shadow-sm transition-shadow hover:shadow-md",
        selected
          ? "border-blue-600 ring-2 ring-blue-200"
          : "border-amber-300"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-amber-500" />

      {/* Folder tab */}
      <div
        className={cn(
          "absolute -top-3 left-2 px-2 py-0.5 rounded-t-md",
          "bg-amber-500 text-white text-[10px] font-bold tracking-wider"
        )}
        aria-hidden="true"
      >
        FIR
      </div>

      <div className="px-3 pt-3 pb-2">
        <p
          className="text-[11px] font-mono font-bold text-amber-900 truncate"
          title={data.firNo}
        >
          {data.firNo}
        </p>
        <div className="mt-1 flex items-center gap-1.5">
          <Icon className="h-3.5 w-3.5 text-amber-700 shrink-0" aria-hidden="true" />
          <p className="text-xs text-amber-900 truncate" title={data.crimeType}>
            {data.crimeType}
          </p>
        </div>
        <p className="mt-0.5 text-[10px] text-amber-700/80">{data.date}</p>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-amber-500" />
    </div>
  );
});
