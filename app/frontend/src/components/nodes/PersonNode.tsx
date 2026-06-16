"use client";

/**
 * PersonNode — investigator-network person node.
 *
 * Visual contract:
 *   - Avatar circle with initials (deterministic from name).
 *   - Name + age + status badge.
 *   - Connection (degree) count chip.
 *   - Status color: arrested=red, suspect=yellow, absconding=orange, unknown=gray.
 *
 * Accessibility:
 *   - `role="group"` + accessible label aggregates name/status/connections for SR.
 *   - All decorative icons set `aria-hidden`.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { User } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonNodeData, PersonStatus } from "@/types/graph";

const STATUS_THEME: Record<
  PersonStatus,
  { ring: string; badge: string; label: string }
> = {
  arrested: {
    ring: "ring-red-500",
    badge: "bg-red-500 text-white",
    label: "Arrested",
  },
  suspect: {
    ring: "ring-yellow-500",
    badge: "bg-yellow-400 text-yellow-950",
    label: "Suspect",
  },
  absconding: {
    ring: "ring-orange-500",
    badge: "bg-orange-500 text-white",
    label: "Absconding",
  },
  unknown: {
    ring: "ring-gray-400",
    badge: "bg-gray-400 text-white",
    label: "Unknown",
  },
};

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("") || "?";
}

export const PersonNode = memo(function PersonNode({
  data,
  selected,
}: NodeProps<PersonNodeData>) {
  const theme = STATUS_THEME[data.status] ?? STATUS_THEME.unknown;
  const connections = data.connectionCount ?? data.firCount;

  return (
    <div
      role="group"
      aria-label={`Person ${data.name}, ${theme.label}, ${connections} connections`}
      className={cn(
        "min-w-[180px] max-w-[220px] rounded-xl border bg-white shadow-sm",
        "px-3 py-2.5 flex items-center gap-3 transition-shadow",
        "hover:shadow-md",
        selected
          ? "border-blue-600 ring-2 ring-blue-200"
          : "border-gray-200"
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />

      <div
        className={cn(
          "shrink-0 h-10 w-10 rounded-full bg-gray-100 grid place-items-center",
          "ring-2",
          theme.ring
        )}
        aria-hidden="true"
      >
        <span className="text-sm font-semibold text-gray-700">
          {initials(data.name)}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-sm font-semibold text-gray-900">
            {data.name}
          </p>
          {typeof data.age === "number" && (
            <span className="text-xs text-gray-500" aria-label={`age ${data.age}`}>
              · {data.age}
            </span>
          )}
        </div>

        <div className="mt-1 flex items-center gap-1.5">
          <span
            className={cn(
              "text-[10px] font-medium px-1.5 py-0.5 rounded-full uppercase tracking-wide",
              theme.badge
            )}
          >
            {theme.label}
          </span>
          <span
            className="inline-flex items-center gap-0.5 text-[10px] text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded-full"
            title={`${connections} connection${connections === 1 ? "" : "s"}`}
          >
            <User className="h-3 w-3" aria-hidden="true" />
            {connections}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
    </div>
  );
});
