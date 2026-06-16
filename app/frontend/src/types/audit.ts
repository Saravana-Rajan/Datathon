/**
 * Audit-chain domain types for KSP Saathi's "Why did you say that?" feature.
 *
 * These types describe the FULL reasoning chain the backend writes to
 * Catalyst NoSQL for every chat turn (see design.md §5.8). They are
 * intentionally richer than the thin `AuditEntry` in `lib/store.ts`,
 * which only carries a summary for chat-list rendering.
 *
 * The drawer hydrates these via GET /server/audit-logger?request_id=...
 * The backend contract is: an array of `AuditStepDTO` objects ordered by
 * `startedAt`. The frontend normalizes them into the discriminated union
 * `AuditStep` for type-safe rendering.
 *
 * IT Act 2008 + DPDP Act 2023 compliance: the chain is immutable on the
 * backend; the UI is read-only and can only flag entries for review.
 */
import type { Language, Role } from "@/lib/store";

// ---------------------------------------------------------------------------
// Step status — drives the green/yellow/red dot color in the timeline.
// ---------------------------------------------------------------------------
export type AuditStatus = "success" | "warning" | "error" | "skipped";

/** Discriminator for the step union. Matches the timeline ordering in §5.8. */
export type AuditStepType =
  | "input"
  | "language"
  | "intent"
  | "tool"
  | "synthesizer"
  | "output";

/** Sub-types for the "tool" step. */
export type AuditToolType =
  | "sql_generator"
  | "cypher_generator"
  | "rag_retriever"
  | "predictive"
  | "geo_lookup"
  | "other";

// ---------------------------------------------------------------------------
// Common fields every step carries.
// ---------------------------------------------------------------------------
export interface AuditStepBase {
  /** Stable id (uuid) — used as React key. */
  id: string;
  /** Human-readable step title shown in the timeline. */
  title: string;
  /** ISO 8601 start time. */
  startedAt: string;
  /** Round-trip latency for the step in milliseconds. */
  latencyMs: number;
  status: AuditStatus;
  /** Free-form note rendered above the details block. */
  note?: string;
}

// ---------------------------------------------------------------------------
// Step 1 — raw user input (Kannada + English transliteration if available).
// ---------------------------------------------------------------------------
export interface AuditInputStep extends AuditStepBase {
  type: "input";
  rawQuery: string;
  /** Optional English transliteration / translation. */
  translatedQuery?: string;
  channel: "voice" | "text";
  userId?: string;
  role?: Role;
}

// ---------------------------------------------------------------------------
// Step 2 — language detection.
// ---------------------------------------------------------------------------
export interface AuditLanguageStep extends AuditStepBase {
  type: "language";
  detected: Language;
  confidence: number; // 0..1
  /** Optional script hint (e.g. "Kannada", "Latin"). */
  script?: string;
  detector?: string;
}

// ---------------------------------------------------------------------------
// Step 3 — intent router decision.
// ---------------------------------------------------------------------------
export interface AuditIntentStep extends AuditStepBase {
  type: "intent";
  intent: string; // e.g. "tabular_query"
  confidence: number; // 0..1
  /** Model that made the decision (Qwen 2.5 7B). */
  model: string;
  /** Tools the router queued for execution. */
  toolPlan: string[];
  entities?: Record<string, string | number | string[]>;
}

// ---------------------------------------------------------------------------
// Step 4 — tool invocations (one entry per tool — usually 1–3 in parallel).
// ---------------------------------------------------------------------------
export interface AuditSqlPayload {
  query: string;
  rowCount: number;
  executionMs: number;
  /** Optional first-row preview (PII-masked by the backend). */
  preview?: Record<string, unknown>[];
}

export interface AuditCypherPayload {
  query: string;
  nodeCount: number;
  edgeCount: number;
  executionMs: number;
}

export interface AuditRagPassage {
  source: string;
  snippet: string;
  similarity: number; // 0..1
  recordId?: string;
}

export interface AuditRagPayload {
  topK: number;
  passages: AuditRagPassage[];
  embedder: string;
}

export interface AuditPredictivePayload {
  model: string;
  forecast: { label: string; value: number; ciLow?: number; ciHigh?: number }[];
  features: string[];
  confidence: number; // 0..1
  /** Explicitly excluded features for ethics audit. */
  excludedFeatures?: string[];
}

export type AuditToolPayload =
  | { kind: "sql"; data: AuditSqlPayload }
  | { kind: "cypher"; data: AuditCypherPayload }
  | { kind: "rag"; data: AuditRagPayload }
  | { kind: "predictive"; data: AuditPredictivePayload }
  | { kind: "raw"; data: unknown };

export interface AuditToolStep extends AuditStepBase {
  type: "tool";
  toolType: AuditToolType;
  toolName: string;
  payload: AuditToolPayload;
}

// ---------------------------------------------------------------------------
// Step 5 — synthesizer (final-answer generation).
// ---------------------------------------------------------------------------
export interface AuditSynthesizerStep extends AuditStepBase {
  type: "synthesizer";
  model: string; // "Qwen 2.5 14B" or "Gemini 2.5 Pro"
  promptTokens: number;
  completionTokens: number;
  /** Why this model was chosen (e.g. "Kannada premium path"). */
  rationale?: string;
}

// ---------------------------------------------------------------------------
// Step 6 — final output.
// ---------------------------------------------------------------------------
export interface AuditOutputStep extends AuditStepBase {
  type: "output";
  answer: string;
  vizSpec?: {
    map?: boolean;
    graph?: boolean;
    chart?: string;
  };
  totalRoundTripMs: number;
  citations?: { source: string; snippet?: string }[];
}

// ---------------------------------------------------------------------------
// Discriminated union over all step types.
// ---------------------------------------------------------------------------
export type AuditStep =
  | AuditInputStep
  | AuditLanguageStep
  | AuditIntentStep
  | AuditToolStep
  | AuditSynthesizerStep
  | AuditOutputStep;

// ---------------------------------------------------------------------------
// Wire-level DTO that comes back from /server/audit-logger.
// `steps` is the canonical timeline; the legacy `summary` mirrors the thin
// `AuditEntry` shape in store.ts for back-compat.
// ---------------------------------------------------------------------------
export interface AuditChain {
  requestId: string;
  sessionId?: string;
  userId?: string;
  role?: Role;
  startedAt: string;
  finishedAt: string;
  totalLatencyMs: number;
  steps: AuditStep[];
  /** Top-level confidence (e.g. synthesizer confidence). */
  confidence?: number;
  /** Compliance: backend mirrors flagged status here. */
  flagged?: boolean;
}

/** POST body for /server/audit-flag — "this answer was wrong" workflow. */
export interface AuditFlagRequest {
  requestId: string;
  reason: string;
  userId?: string;
  /** Optional pointer to the suspect step (e.g. SQL generator). */
  suspectStepId?: string;
}
