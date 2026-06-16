"use client";

/**
 * NetworkGraph — criminal-network visualization (Feature 5.5).
 *
 * Reads `graphNodes` + `graphEdges` from the Zustand store and renders them
 * as a React Flow graph with three custom node types (person/fir/station)
 * and four edge styles (KNOWS, ACCUSED_IN, CO_ARRESTED, CALLS).
 *
 * Notable behaviours:
 *   - Force-ish layered auto-layout via `lib/graph-layout.ts`.
 *   - When the graph data identity changes (new traversal result lands), edges
 *     reveal sequentially at 200ms each so the user can watch the traversal.
 *   - Hover any node → tooltip with rich details + recent FIRs.
 *   - Click any node → emits `onNodeContext({ nodeId, payload })` so the parent
 *     can wire an "Add to chat context" action.
 *   - Path highlight mode: toggle the toolbar button, click two nodes, the
 *     shortest path between them is highlighted.
 *   - Minimap + zoom/pan controls + fit-to-view button.
 *
 * Store mapping: the store exposes generic GraphNode/GraphEdge with a free-form
 * `properties` map. This component is the *adapter* — it reads
 * `node.properties` for typed node data and `edge.properties.type` for edge
 * kind. That lets the backend remain flexible while the viz layer stays typed.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type NodeTypes,
  type EdgeTypes,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";

import { useKspStore, type GraphEdge as StoreGraphEdge, type GraphNode as StoreGraphNode } from "@/lib/store";
import {
  layoutNodes,
  shortestPath,
  edgesOnPath,
  type LayoutDirection,
} from "@/lib/graph-layout";
import { animateEdgeReveal, pulseNode } from "@/lib/graph-animations";
import { cn } from "@/lib/utils";
import {
  Route,
  ZoomIn,
  Crosshair,
  X,
} from "lucide-react";

import { PersonNode } from "./nodes/PersonNode";
import { FIRNode } from "./nodes/FIRNode";
import { StationNode } from "./nodes/StationNode";

import type {
  GraphEdgeKind,
  GraphRFEdge,
  GraphRFNode,
  NodeContextEvent,
  PersonNodeData,
  FIRNodeData,
  StationNodeData,
} from "@/types/graph";

// ---------- Static React Flow registries -----------------------------------

// Defined at module scope so React Flow doesn't see new identity on every
// render (which would trigger its dev warning about node-type recreation).
const NODE_TYPES: NodeTypes = {
  person: PersonNode,
  fir: FIRNode,
  station: StationNode,
};

// We don't need custom edge components — variant styling is enough.
const EDGE_TYPES: EdgeTypes = {};

// ---------- Edge variant theme ---------------------------------------------

const EDGE_STYLE: Record<
  GraphEdgeKind,
  { stroke: string; dashed?: boolean; label: string }
> = {
  KNOWS:       { stroke: "#9ca3af", label: "knows" },                    // gray-400
  ACCUSED_IN:  { stroke: "#dc2626", label: "accused in" },               // red-600
  CO_ARRESTED: { stroke: "#9333ea", label: "co-arrested" },              // purple-600
  CALLS:       { stroke: "#2563eb", dashed: true, label: "calls" },      // blue-600 dashed
};

function edgeKindFrom(props: StoreGraphEdge["properties"] | undefined): GraphEdgeKind {
  const raw = (props?.type ?? "").toString().toUpperCase();
  if (raw === "KNOWS" || raw === "ACCUSED_IN" || raw === "CO_ARRESTED" || raw === "CALLS") {
    return raw;
  }
  return "KNOWS";
}

function styleForEdgeKind(kind: GraphEdgeKind, dimmed = false, highlighted = false) {
  const s = EDGE_STYLE[kind];
  const style: CSSProperties = {
    stroke: s.stroke,
    strokeWidth: highlighted ? 3 : 1.75,
    opacity: dimmed ? 0.18 : 1,
    strokeDasharray: s.dashed ? "6 4" : undefined,
  };
  return style;
}

// ---------- Store → React Flow adapter -------------------------------------

interface AdapterInput {
  storeNodes: StoreGraphNode[];
  storeEdges: StoreGraphEdge[];
}

function adaptNode(n: StoreGraphNode): GraphRFNode {
  const props = n.properties ?? {};
  switch (n.type) {
    case "person": {
      const data: PersonNodeData = {
        name: (props.name as string) ?? n.label,
        age: typeof props.age === "number" ? (props.age as number) : undefined,
        status:
          (props.status as PersonNodeData["status"]) ??
          (typeof props.arrested === "boolean"
            ? (props.arrested ? "arrested" : "suspect")
            : "unknown"),
        phone: (props.phone as string) ?? undefined,
        firCount:
          typeof props.firCount === "number" ? (props.firCount as number) : 0,
        connectionCount:
          typeof props.connectionCount === "number"
            ? (props.connectionCount as number)
            : undefined,
        recentFirs: Array.isArray(
          (props as unknown as { recentFirs?: unknown }).recentFirs
        )
          ? ((props as unknown as { recentFirs: PersonNodeData["recentFirs"] }).recentFirs)
          : undefined,
      };
      return {
        id: n.id,
        type: "person",
        data,
        position: { x: 0, y: 0 },
      };
    }
    case "fir": {
      const data: FIRNodeData = {
        firNo: (props.firNo as string) ?? n.label,
        crimeType: (props.crimeType as string) ?? "Unknown",
        date: (props.date as string) ?? "",
        station: (props.station as string) ?? undefined,
        sections: Array.isArray((props as unknown as { sections?: unknown }).sections)
          ? ((props as unknown as { sections: string[] }).sections)
          : undefined,
      };
      return { id: n.id, type: "fir", data, position: { x: 0, y: 0 } };
    }
    case "location":
    case "phone":
    case "vehicle":
    default: {
      // The current store uses these for non-station entity nodes; we still
      // need to render them — treat as station-style institutional node for
      // visual consistency. (Real station nodes are emitted with type "station"
      // — the store enum will be widened when that lands.)
      const data: StationNodeData = {
        name: (props.name as string) ?? n.label,
        district: (props.district as string) ?? undefined,
        firCount:
          typeof props.firCount === "number"
            ? (props.firCount as number)
            : undefined,
      };
      return { id: n.id, type: "station", data, position: { x: 0, y: 0 } };
    }
  }
}

function adaptEdge(e: StoreGraphEdge): GraphRFEdge {
  const kind = edgeKindFrom(e.properties);
  const theme = EDGE_STYLE[kind];
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label || theme.label,
    type: "default",
    animated: false,
    hidden: false, // we toggle visibility via opacity during reveal
    style: styleForEdgeKind(kind),
    labelStyle: { fill: theme.stroke, fontSize: 10, fontWeight: 600 },
    labelBgStyle: { fill: "white", fillOpacity: 0.85 },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: theme.stroke,
      width: 16,
      height: 16,
    },
    data: { type: kind, weight: typeof e.properties?.weight === "number" ? (e.properties.weight as number) : undefined },
  };
}

function adaptAll({ storeNodes, storeEdges }: AdapterInput) {
  const nodes = storeNodes.map(adaptNode);
  const edges = storeEdges.map(adaptEdge);
  return { nodes, edges };
}

// ---------- Tooltip --------------------------------------------------------

interface HoverTooltipState {
  x: number;
  y: number;
  node: GraphRFNode;
}

function NodeTooltip({ state }: { state: HoverTooltipState }) {
  const { node, x, y } = state;
  return (
    <div
      className="pointer-events-none absolute z-50 max-w-[260px] rounded-md border border-gray-200 bg-white p-2.5 shadow-lg text-xs"
      style={{ left: x + 12, top: y + 12 }}
      role="tooltip"
    >
      {node.type === "person" && (
        <>
          <p className="font-semibold text-gray-900">
            {(node.data as PersonNodeData).name}
            {typeof (node.data as PersonNodeData).age === "number" && (
              <span className="text-gray-500 font-normal">
                {" "}· {(node.data as PersonNodeData).age}y
              </span>
            )}
          </p>
          <p className="mt-0.5 text-gray-600 capitalize">
            Status: {(node.data as PersonNodeData).status}
          </p>
          {(node.data as PersonNodeData).phone && (
            <p className="text-gray-600 font-mono text-[11px]">
              {(node.data as PersonNodeData).phone}
            </p>
          )}
          <p className="text-gray-600">
            {(node.data as PersonNodeData).firCount} FIR
            {(node.data as PersonNodeData).firCount === 1 ? "" : "s"}
          </p>
          {(node.data as PersonNodeData).recentFirs?.length ? (
            <div className="mt-1.5 border-t pt-1.5">
              <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">
                Recent FIRs
              </p>
              <ul className="space-y-0.5">
                {(node.data as PersonNodeData).recentFirs!.slice(0, 3).map((f) => (
                  <li key={f.firNo} className="text-[11px] text-gray-700">
                    <span className="font-mono">{f.firNo}</span> · {f.crimeType}{" "}
                    <span className="text-gray-500">({f.date})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
      {node.type === "fir" && (
        <>
          <p className="font-semibold text-gray-900 font-mono">
            {(node.data as FIRNodeData).firNo}
          </p>
          <p className="text-gray-600">{(node.data as FIRNodeData).crimeType}</p>
          <p className="text-gray-500">{(node.data as FIRNodeData).date}</p>
          {(node.data as FIRNodeData).station && (
            <p className="text-gray-500">
              Station: {(node.data as FIRNodeData).station}
            </p>
          )}
          {(node.data as FIRNodeData).sections?.length ? (
            <p className="mt-1 text-[11px] text-gray-700">
              Sections: {(node.data as FIRNodeData).sections!.join(", ")}
            </p>
          ) : null}
        </>
      )}
      {node.type === "station" && (
        <>
          <p className="font-semibold text-blue-950">
            {(node.data as StationNodeData).name}
          </p>
          {(node.data as StationNodeData).district && (
            <p className="text-gray-600">
              {(node.data as StationNodeData).district}
            </p>
          )}
          {typeof (node.data as StationNodeData).firCount === "number" && (
            <p className="text-gray-600">
              {(node.data as StationNodeData).firCount} active FIR
              {(node.data as StationNodeData).firCount === 1 ? "" : "s"}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ---------- Legend ---------------------------------------------------------

function Legend() {
  return (
    <div className="absolute bottom-3 left-3 z-10 rounded-md border border-gray-200 bg-white/95 backdrop-blur px-3 py-2 shadow-sm">
      <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">
        Edges
      </p>
      <ul className="space-y-1 text-[11px] text-gray-700">
        {(Object.keys(EDGE_STYLE) as GraphEdgeKind[]).map((k) => (
          <li key={k} className="flex items-center gap-2">
            <svg width="28" height="6" aria-hidden="true">
              <line
                x1="0"
                y1="3"
                x2="28"
                y2="3"
                stroke={EDGE_STYLE[k].stroke}
                strokeWidth="2"
                strokeDasharray={EDGE_STYLE[k].dashed ? "5 3" : undefined}
              />
            </svg>
            <span>{EDGE_STYLE[k].label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------- Public props ---------------------------------------------------

export interface NetworkGraphProps {
  /** Layout direction; default LR (left → right). */
  direction?: LayoutDirection;
  /** Emitted when the user clicks a node ("Add to chat context"). */
  onNodeContext?: (event: NodeContextEvent) => void;
  /** Tailwind classes for the outer container; pass `h-...` and `w-...`. */
  className?: string;
  /** Per-edge reveal delay in ms; default 200. */
  revealStepMs?: number;
}

// ---------- Component ------------------------------------------------------

export function NetworkGraph({
  direction = "LR",
  onNodeContext,
  className,
  revealStepMs = 200,
}: NetworkGraphProps) {
  const storeNodes = useKspStore((s) => s.graphNodes);
  const storeEdges = useKspStore((s) => s.graphEdges);

  // Adapt store → React Flow shapes whenever the source changes.
  const adapted = useMemo(
    () => adaptAll({ storeNodes, storeEdges }),
    [storeNodes, storeEdges]
  );

  // Layout once per data identity.
  const laidOut = useMemo(
    () => ({
      nodes: layoutNodes(adapted.nodes, adapted.edges, direction),
      edges: adapted.edges,
    }),
    [adapted, direction]
  );

  // Local copies — we mutate `edges` during animated reveal.
  const [nodes, setNodes] = useState<Node[]>(laidOut.nodes);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Hover tooltip + path-highlight state.
  const [tooltip, setTooltip] = useState<HoverTooltipState | null>(null);
  const [pathMode, setPathMode] = useState(false);
  const [pathSelection, setPathSelection] = useState<string[]>([]);
  const [highlightedPath, setHighlightedPath] = useState<{
    nodes: Set<string>;
    edges: Set<string>;
  } | null>(null);

  const rfRef = useRef<ReactFlowInstance | null>(null);
  const revealHandleRef = useRef<{ cancel: () => void } | null>(null);

  // When the graph data identity changes, replay the reveal.
  useEffect(() => {
    // Cancel any in-flight reveal first so we don't double-animate.
    revealHandleRef.current?.cancel();

    setNodes(laidOut.nodes);
    // Start with all edges hidden (opacity 0) — reveal them one by one.
    const initialEdges = laidOut.edges.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: 0 },
    }));
    setEdges(initialEdges);

    const handle = animateEdgeReveal(
      laidOut.edges,
      (edge) => {
        setEdges((prev) =>
          prev.map((e) =>
            e.id === edge.id
              ? {
                  ...e,
                  animated: true,
                  style: { ...(edge.style ?? {}), opacity: 1 },
                }
              : e
          )
        );
        // Pulse the target node as the edge arrives — feels like the traversal
        // is "walking" through the graph.
        if (edge.target) pulseNode(edge.target);
      },
      revealStepMs
    );
    revealHandleRef.current = handle;

    // After reveal completes, stop the animated flow on edges.
    handle.done.then(() => {
      setEdges((prev) =>
        prev.map((e) => ({ ...e, animated: false }))
      );
    });

    return () => handle.cancel();
  }, [laidOut, revealStepMs]);

  // Re-apply path-highlight styling when selection changes.
  useEffect(() => {
    if (!highlightedPath) {
      // Restore all edges to full opacity.
      setEdges((prev) =>
        prev.map((e) => ({
          ...e,
          style: {
            ...(e.style ?? {}),
            opacity: 1,
            strokeWidth: 1.75,
          },
        }))
      );
      return;
    }
    setEdges((prev) =>
      prev.map((e) => {
        const kind = (e.data?.type as GraphEdgeKind | undefined) ?? "KNOWS";
        const isOn = highlightedPath.edges.has(e.id ?? "");
        return {
          ...e,
          style: styleForEdgeKind(kind, !isOn, isOn),
        };
      })
    );
  }, [highlightedPath]);

  // Hover handlers.
  const onNodeMouseEnter: NodeMouseHandler = useCallback((evt, node) => {
    setTooltip({
      x: (evt as unknown as MouseEvent).clientX,
      y: (evt as unknown as MouseEvent).clientY,
      node: node as GraphRFNode,
    });
  }, []);

  const onNodeMouseMove: NodeMouseHandler = useCallback((evt, node) => {
    setTooltip({
      x: (evt as unknown as MouseEvent).clientX,
      y: (evt as unknown as MouseEvent).clientY,
      node: node as GraphRFNode,
    });
  }, []);

  const onNodeMouseLeave: NodeMouseHandler = useCallback(() => {
    setTooltip(null);
  }, []);

  // Click handler: either path-mode selection, or emit-context.
  const onNodeClick: NodeMouseHandler = useCallback(
    (_evt, node) => {
      if (pathMode) {
        setPathSelection((prev) => {
          const next = prev.length >= 2 ? [node.id] : [...prev, node.id];
          if (next.length === 2) {
            const path = shortestPath(
              storeNodes,
              storeEdges,
              next[0],
              next[1]
            );
            if (path) {
              setHighlightedPath({
                nodes: new Set(path),
                edges: edgesOnPath(edges, path),
              });
            } else {
              setHighlightedPath(null);
            }
          } else {
            setHighlightedPath(null);
          }
          return next;
        });
        return;
      }
      if (!onNodeContext) return;
      const rf = node as GraphRFNode;
      onNodeContext({
        nodeId: rf.id,
        nodeType: rf.type as NodeContextEvent["nodeType"],
        label:
          rf.type === "person"
            ? (rf.data as PersonNodeData).name
            : rf.type === "fir"
              ? (rf.data as FIRNodeData).firNo
              : (rf.data as StationNodeData).name,
        payload: rf.data as unknown as Record<string, unknown>,
      });
    },
    [pathMode, onNodeContext, storeNodes, storeEdges, edges]
  );

  // Toolbar handlers.
  const fitView = useCallback(() => {
    rfRef.current?.fitView({ padding: 0.2, duration: 400 });
  }, []);

  const togglePathMode = useCallback(() => {
    setPathMode((m) => {
      if (m) {
        // Leaving path mode — clear selection + highlight.
        setPathSelection([]);
        setHighlightedPath(null);
      }
      return !m;
    });
  }, []);

  const clearHighlight = useCallback(() => {
    setPathSelection([]);
    setHighlightedPath(null);
  }, []);

  // Empty-state.
  if (nodes.length === 0) {
    return (
      <div
        className={cn(
          "relative flex h-full w-full items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500",
          className
        )}
      >
        <div className="text-center">
          <p className="font-medium text-gray-700">No network loaded</p>
          <p className="mt-1 text-xs">
            Ask a question like &quot;Show me everyone connected to Ravi&quot; to
            populate the graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative h-full w-full", className)}>
      {/* Local CSS for the pulse animation (kept inline so no extra global file). */}
      <style jsx global>{`
        .ksp-node-pulse {
          animation: ksp-pulse 0.9s ease-out 1;
        }
        @keyframes ksp-pulse {
          0%   { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.55); }
          70%  { box-shadow: 0 0 0 14px rgba(37, 99, 235, 0); }
          100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
        }
      `}</style>

      {/* Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1 rounded-md border border-gray-200 bg-white/95 p-1 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={fitView}
          className="inline-flex h-8 items-center gap-1 rounded px-2 text-xs font-medium text-gray-700 hover:bg-gray-100"
          aria-label="Fit graph to view"
          title="Fit to view"
        >
          <ZoomIn className="h-3.5 w-3.5" aria-hidden="true" />
          Fit
        </button>
        <button
          type="button"
          onClick={togglePathMode}
          className={cn(
            "inline-flex h-8 items-center gap-1 rounded px-2 text-xs font-medium",
            pathMode
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "text-gray-700 hover:bg-gray-100"
          )}
          aria-pressed={pathMode}
          aria-label="Toggle shortest-path highlight mode"
          title="Highlight path: click two nodes"
        >
          <Route className="h-3.5 w-3.5" aria-hidden="true" />
          Path
        </button>
        {highlightedPath && (
          <button
            type="button"
            onClick={clearHighlight}
            className="inline-flex h-8 items-center gap-1 rounded px-2 text-xs font-medium text-gray-700 hover:bg-gray-100"
            aria-label="Clear highlighted path"
            title="Clear highlight"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            Clear
          </button>
        )}
      </div>

      {/* Path-mode hint */}
      {pathMode && (
        <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-[11px] font-medium text-blue-800 shadow-sm">
          <Crosshair className="mr-1 inline h-3 w-3 align-text-bottom" aria-hidden="true" />
          {pathSelection.length === 0 && "Click the start node…"}
          {pathSelection.length === 1 && "Now click the end node…"}
          {pathSelection.length === 2 &&
            (highlightedPath
              ? `Path: ${highlightedPath.nodes.size} nodes`
              : "No path found")}
        </div>
      )}

      <ReactFlow
        nodes={nodes.map((n) => ({
          ...n,
          selected: highlightedPath?.nodes.has(n.id) ?? false,
        }))}
        edges={edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseMove={onNodeMouseMove}
        onNodeMouseLeave={onNodeMouseLeave}
        onNodeClick={onNodeClick}
        onInit={(instance) => {
          rfRef.current = instance;
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        minZoom={0.2}
        maxZoom={2}
      >
        <Background gap={20} size={1} color="#e5e7eb" />
        <Controls
          showInteractive={false}
          className="!bg-white !border !border-gray-200 !rounded-md !shadow-sm"
        />
        <MiniMap
          pannable
          zoomable
          nodeStrokeWidth={2}
          nodeColor={(n) => {
            if (n.type === "person") {
              const status = (n.data as PersonNodeData).status;
              return status === "arrested"
                ? "#dc2626"
                : status === "suspect"
                  ? "#eab308"
                  : status === "absconding"
                    ? "#f97316"
                    : "#9ca3af";
            }
            if (n.type === "fir") return "#f59e0b";
            return "#2563eb";
          }}
          maskColor="rgba(243, 244, 246, 0.7)"
          className="!bg-white !border !border-gray-200 !rounded-md !shadow-sm"
        />
      </ReactFlow>

      <Legend />
      {tooltip && <NodeTooltip state={tooltip} />}
    </div>
  );
}

export default NetworkGraph;
