/**
 * Graph type contracts for the NetworkGraph visualization.
 *
 * The Zustand store (`lib/store.ts`) holds generic GraphNode/GraphEdge shapes
 * with a free-form `properties` map. The NetworkGraph adapter narrows those
 * generic shapes into the typed data below before handing them to React Flow.
 *
 * Why we mirror & extend instead of replacing the store types:
 *   - Store stays small and protocol-friendly (anything Catalyst Functions or
 *     the Cypher generator returns can land in `properties`).
 *   - The visualization layer gets strict, exhaustive node-data unions so
 *     React Flow custom nodes are fully typed.
 */

import type { Node, Edge } from "reactflow";

// ---------- Node data (per node type) --------------------------------------

export type PersonStatus =
  | "arrested"
  | "suspect"
  | "absconding"
  | "unknown";

export interface PersonNodeData {
  name: string;
  age?: number;
  status: PersonStatus;
  phone?: string;
  /** Number of FIRs this person is connected to. Drives the badge. */
  firCount: number;
  /** Optional recent FIR refs surfaced in the hover tooltip. */
  recentFirs?: { firNo: string; crimeType: string; date: string }[];
  /** Pre-computed connection (degree) count for quick render. */
  connectionCount?: number;
}

export interface FIRNodeData {
  firNo: string;
  crimeType: string;
  date: string;
  station?: string;
  /** IPC / BNS sections, surfaced in tooltip. */
  sections?: string[];
}

export interface StationNodeData {
  name: string;
  district?: string;
  /** Number of active FIRs handled by this station. */
  firCount?: number;
}

// ---------- Edge type union -------------------------------------------------

export type GraphEdgeKind =
  | "KNOWS"
  | "ACCUSED_IN"
  | "CO_ARRESTED"
  | "CALLS";

export interface GraphEdgeData {
  type: GraphEdgeKind;
  weight?: number;
  /** Optional metadata (e.g. call count, FIR reference) shown on hover. */
  meta?: Record<string, string | number>;
}

// ---------- The shape callers should construct -----------------------------

/**
 * A typed graph edge as produced by the Cypher generator / store adapter,
 * before React Flow normalization. This is the input contract for
 * `layoutNodes(...)` and animation helpers.
 */
export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  type: GraphEdgeKind;
  weight?: number;
}

// ---------- React Flow specialized node/edge unions ------------------------

export type PersonRFNode = Node<PersonNodeData, "person">;
export type FIRRFNode = Node<FIRNodeData, "fir">;
export type StationRFNode = Node<StationNodeData, "station">;

export type GraphRFNode = PersonRFNode | FIRRFNode | StationRFNode;
export type GraphRFEdge = Edge<GraphEdgeData>;

// ---------- Events emitted to the parent -----------------------------------

export interface NodeContextEvent {
  nodeId: string;
  nodeType: "person" | "fir" | "station";
  label: string;
  /** Compact context payload suitable for "Add to chat context". */
  payload: Record<string, unknown>;
}
