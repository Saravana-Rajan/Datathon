"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  FileDown,
  Flag,
  HelpCircle,
  Loader2,
  ShieldCheck,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  auditChainToMarkdown,
  downloadBlob,
  formatLatency,
  formatConfidence,
  getStatusTheme,
} from "@/lib/audit-format";
import { ApiError, exportPdf, getAuditTrail } from "@/lib/api";
import { useKspStore, type AuditEntry } from "@/lib/store";
import { cn } from "@/lib/utils";
import type {
  AuditChain,
  AuditStatus,
  AuditStep as AuditStepDTO,
} from "@/types/audit";

import { AuditStep } from "./AuditStep";
import { AuditTimeline } from "./AuditTimeline";

// ---------------------------------------------------------------------------
// API shim — the backend audit-logger function is still being built. We
// accept either the rich AuditChain shape (what we want) or the thin
// legacy AuditEntry[] shape (what `lib/api.ts` types today) and normalize.
// ---------------------------------------------------------------------------
function looksLikeChain(value: unknown): value is AuditChain {
  return (
    typeof value === "object" &&
    value !== null &&
    "steps" in value &&
    Array.isArray((value as { steps: unknown }).steps)
  );
}

function legacyToChain(entries: AuditEntry[], requestId: string): AuditChain {
  // The thin AuditEntry shape only carries a single summary line per turn.
  // Build a minimal AuditChain so the drawer still renders something useful.
  const e = entries.find((x) => x.requestId === requestId) ?? entries[0];
  const now = new Date().toISOString();
  const steps: AuditStepDTO[] = [];
  if (e) {
    steps.push({
      id: `${e.requestId}-intent`,
      type: "intent",
      title: "Intent classified",
      startedAt: e.timestamp,
      latencyMs: 0,
      status: "success",
      intent: e.intent,
      confidence: e.confidence ?? 0.8,
      model: "Qwen 2.5 7B (Catalyst QuickML)",
      toolPlan: e.toolCalls ?? [],
    });
    if (e.toolCalls && e.toolCalls.length > 0) {
      e.toolCalls.forEach((t, i) =>
        steps.push({
          id: `${e.requestId}-tool-${i}`,
          type: "tool",
          title: `Tool: ${t}`,
          startedAt: e.timestamp,
          latencyMs: 0,
          status: "success",
          toolType: "other",
          toolName: t,
          payload: { kind: "raw", data: { note: "Details not captured by legacy log" } },
        }),
      );
    }
    steps.push({
      id: `${e.requestId}-output`,
      type: "output",
      title: "Answer delivered",
      startedAt: e.timestamp,
      latencyMs: 0,
      status: "success",
      answer: e.summary,
      totalRoundTripMs: 0,
      citations: e.sources?.map((s) => ({ source: s })),
    });
  }
  return {
    requestId,
    startedAt: e?.timestamp ?? now,
    finishedAt: now,
    totalLatencyMs: 0,
    steps,
    confidence: e?.confidence,
  };
}

async function fetchAuditChain(requestId: string): Promise<AuditChain> {
  // `getAuditTrail` is typed as `AuditEntry[]` today but the real backend
  // will return the richer chain — handle both.
  const raw = (await getAuditTrail(requestId)) as unknown;
  if (looksLikeChain(raw)) return raw;
  if (Array.isArray(raw)) return legacyToChain(raw as AuditEntry[], requestId);
  if (raw && typeof raw === "object" && "chain" in raw) {
    const c = (raw as { chain: unknown }).chain;
    if (looksLikeChain(c)) return c;
  }
  throw new Error("Unrecognized audit-trail payload shape");
}

// ---------------------------------------------------------------------------
// Top-level health pill — green/yellow/red based on the worst step.
// ---------------------------------------------------------------------------
function deriveHealth(chain: AuditChain | null): AuditStatus {
  if (!chain || chain.steps.length === 0) return "warning";
  if (chain.steps.some((s) => s.status === "error")) return "error";
  if (chain.steps.some((s) => s.status === "warning")) return "warning";
  return "success";
}

function HealthPill({ status }: { status: AuditStatus }): JSX.Element {
  const theme = getStatusTheme(status);
  const Icon =
    status === "error"
      ? AlertTriangle
      : status === "warning"
        ? AlertTriangle
        : CheckCircle2;
  const label =
    status === "error"
      ? "Errors detected"
      : status === "warning"
        ? "Review recommended"
        : "All checks passed";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        theme.badge,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Drawer trigger — drop this next to any assistant message.
// ---------------------------------------------------------------------------
export interface AuditDrawerTriggerProps {
  requestId: string;
  onOpen: (requestId: string) => void;
  className?: string;
  /** Optional override label — default is "Why?". */
  label?: string;
}

export function AuditDrawerTrigger({
  requestId,
  onOpen,
  className,
  label = "Why?",
}: AuditDrawerTriggerProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onOpen(requestId)}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5",
        "text-[11px] font-medium text-muted-foreground transition-colors",
        "hover:border-primary/40 hover:bg-primary/5 hover:text-primary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      aria-label="Why did Sarvik say that? Open audit trail"
    >
      <HelpCircle className="h-3 w-3" aria-hidden="true" />
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Body states
// ---------------------------------------------------------------------------
function LoadingState(): JSX.Element {
  return (
    <div className="flex flex-1 items-center justify-center py-12 text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
      Fetching audit trail…
    </div>
  );
}

function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}): JSX.Element {
  const message =
    error instanceof ApiError && error.status !== 0
      ? `${error.message} (HTTP ${error.status})`
      : error.message;
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-rose-500" aria-hidden="true" />
      <div className="max-w-xs text-sm text-muted-foreground">{message}</div>
      <Button size="sm" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main drawer component
// ---------------------------------------------------------------------------
export interface AuditDrawerProps {
  /** The request_id of the assistant turn being explained. `null` = closed. */
  requestId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AuditDrawer({
  requestId,
  open,
  onOpenChange,
}: AuditDrawerProps): JSX.Element | null {
  const [chain, setChain] = React.useState<AuditChain | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);
  const [copyState, setCopyState] = React.useState<"idle" | "copied" | "error">(
    "idle",
  );
  const [flagState, setFlagState] = React.useState<"idle" | "open" | "submitting" | "submitted">(
    "idle",
  );
  const [flagReason, setFlagReason] = React.useState("");
  const [pdfState, setPdfState] = React.useState<"idle" | "exporting">("idle");

  const sessionId = useKspStore((s) => s.sessionId);
  const userId = useKspStore((s) => s.userId);

  // ----- data fetch -------------------------------------------------------
  const load = React.useCallback(async () => {
    if (!requestId) return;
    setLoading(true);
    setError(null);
    try {
      const c = await fetchAuditChain(requestId);
      setChain(c);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  React.useEffect(() => {
    if (open && requestId) {
      void load();
    } else if (!open) {
      // reset transient UI state when the drawer closes
      setFlagState("idle");
      setFlagReason("");
      setCopyState("idle");
    }
  }, [open, requestId, load]);

  // ----- escape-to-close + focus management -------------------------------
  const drawerRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    // Lock body scroll behind the drawer
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Focus the drawer for screen readers
    drawerRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onOpenChange]);

  // ----- actions ----------------------------------------------------------
  const handleCopyEvidence = React.useCallback(async () => {
    if (!chain) return;
    try {
      const md = auditChainToMarkdown(chain);
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(md);
        setCopyState("copied");
        setTimeout(() => setCopyState("idle"), 1800);
      } else {
        // Fallback — surface as download
        downloadBlob(
          new Blob([md], { type: "text/markdown;charset=utf-8" }),
          `audit-${chain.requestId}.md`,
        );
        setCopyState("copied");
      }
    } catch {
      setCopyState("error");
      setTimeout(() => setCopyState("idle"), 1800);
    }
  }, [chain]);

  const handleDownloadMarkdown = React.useCallback(() => {
    if (!chain) return;
    const md = auditChainToMarkdown(chain);
    downloadBlob(
      new Blob([md], { type: "text/markdown;charset=utf-8" }),
      `audit-${chain.requestId}.md`,
    );
  }, [chain]);

  const handleExportPdf = React.useCallback(async () => {
    if (!chain) return;
    setPdfState("exporting");
    try {
      // Catalyst SmartBrowz powers the PDF render — see design.md §6 + §10.
      const sid = sessionId ?? chain.sessionId ?? chain.requestId;
      const blob = await exportPdf(sid);
      downloadBlob(blob, `audit-${chain.requestId}.pdf`);
    } catch (e) {
      console.error("PDF export failed", e);
    } finally {
      setPdfState("idle");
    }
  }, [chain, sessionId]);

  const handleSubmitFlag = React.useCallback(async () => {
    if (!chain || !flagReason.trim()) return;
    setFlagState("submitting");
    try {
      const base = (process.env.NEXT_PUBLIC_CATALYST_API ?? "").replace(/\/+$/, "");
      if (!base) throw new ApiError(0, "NEXT_PUBLIC_CATALYST_API not set");
      const res = await fetch(`${base}/server/audit-flag`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          requestId: chain.requestId,
          reason: flagReason.trim(),
          userId: userId ?? undefined,
        }),
      });
      if (!res.ok) throw new ApiError(res.status, `Flag failed: ${res.status}`);
      setFlagState("submitted");
    } catch (e) {
      console.error("Flag submission failed", e);
      setFlagState("idle");
    }
  }, [chain, flagReason, userId]);

  if (!open) return null;

  const health = deriveHealth(chain);

  return (
    <div
      className="fixed inset-0 z-50 flex"
      aria-hidden={!open}
      role="presentation"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close audit drawer"
        onClick={() => onOpenChange(false)}
        className={cn(
          "absolute inset-0 bg-slate-950/40 backdrop-blur-sm",
          "transition-opacity duration-200",
          "data-[state=open]:opacity-100",
        )}
        data-state={open ? "open" : "closed"}
      />

      {/* Drawer panel */}
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="audit-drawer-title"
        tabIndex={-1}
        className={cn(
          "relative ml-auto flex h-full w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl",
          "animate-in slide-in-from-right",
          "focus:outline-none",
        )}
        style={{
          // Tailwind doesn't ship slide-in animation utilities by default;
          // inline keyframes give us the same effect with zero config drift.
          animation: "ksp-audit-slide-in 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        {/* Header */}
        <header className="flex items-start justify-between gap-3 border-b border-border bg-gradient-to-br from-primary/5 via-background to-background px-5 py-4">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex h-7 w-7 items-center justify-center rounded-md",
                  "bg-primary/10 text-primary",
                )}
                aria-hidden="true"
              >
                <ShieldCheck className="h-4 w-4" />
              </span>
              <h2
                id="audit-drawer-title"
                className="text-base font-semibold leading-none"
              >
                Why did Sarvik say that?
              </h2>
            </div>
            <p className="text-[12px] text-muted-foreground">
              Full reasoning chain · IT Act 2008 §65B compliant audit log
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <HealthPill status={health} />
              {chain ? (
                <>
                  <span className="text-[11px] font-mono text-muted-foreground">
                    {formatLatency(chain.totalLatencyMs)} total
                  </span>
                  {chain.confidence !== undefined ? (
                    <span className="text-[11px] font-mono text-muted-foreground">
                      · conf {formatConfidence(chain.confidence)}
                    </span>
                  ) : null}
                  <span className="text-[11px] font-mono text-muted-foreground">
                    · req {chain.requestId.slice(0, 8)}…
                  </span>
                </>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className={cn(
              "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground",
              "hover:bg-muted hover:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
            aria-label="Close audit drawer"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        {/* Body */}
        <div className="flex flex-1 flex-col overflow-y-auto px-5 py-4">
          {loading ? <LoadingState /> : null}
          {!loading && error ? <ErrorState error={error} onRetry={load} /> : null}
          {!loading && !error && chain ? (
            chain.steps.length === 0 ? (
              <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                No audit steps recorded for this request.
              </div>
            ) : (
              <AuditTimeline>
                {chain.steps.map((step, i) => (
                  <AuditStep
                    key={step.id}
                    step={step}
                    index={i}
                    // Auto-expand input + output (most useful at a glance).
                    defaultExpanded={step.type === "input" || step.type === "output"}
                  />
                ))}
              </AuditTimeline>
            )
          ) : null}
        </div>

        {/* Action bar */}
        <footer className="border-t border-border bg-muted/40 px-5 py-3">
          {flagState === "open" ? (
            <div className="space-y-2">
              <label
                htmlFor="audit-flag-reason"
                className="block text-[12px] font-medium"
              >
                What was wrong with this answer?
              </label>
              <textarea
                id="audit-flag-reason"
                value={flagReason}
                onChange={(e) => setFlagReason(e.target.value)}
                rows={3}
                placeholder="e.g. SQL filtered on the wrong district; predicted hotspot didn't match the actual map area…"
                className={cn(
                  "w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-[13px]",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              />
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setFlagState("idle");
                    setFlagReason("");
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={!flagReason.trim() || flagState !== "open"}
                  onClick={handleSubmitFlag}
                >
                  Send to bias-review queue
                </Button>
              </div>
            </div>
          ) : flagState === "submitted" ? (
            <div className="flex items-center justify-between gap-3 text-[12px]">
              <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Flagged for review. Thank you — this strengthens the model.
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setFlagState("idle")}
              >
                Close
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={handleCopyEvidence}
                disabled={!chain}
                aria-label="Copy the full audit chain as Markdown evidence"
              >
                <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                {copyState === "copied"
                  ? "Copied"
                  : copyState === "error"
                    ? "Copy failed"
                    : "Copy as evidence"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleDownloadMarkdown}
                disabled={!chain}
                aria-label="Download audit trail as Markdown file"
              >
                <Download className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                .md
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleExportPdf}
                disabled={!chain || pdfState === "exporting"}
                aria-label="Export audit trail to PDF via SmartBrowz"
              >
                {pdfState === "exporting" ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <FileDown className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                )}
                PDF
              </Button>
              <div className="ml-auto" />
              <Button
                size="sm"
                variant="outline"
                onClick={() => setFlagState("open")}
                disabled={!chain}
                aria-label="Flag this answer as wrong for the bias review board"
                className="border-rose-500/30 text-rose-600 hover:bg-rose-500/10 dark:text-rose-300"
              >
                <Flag className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                Flag wrong
              </Button>
            </div>
          )}
        </footer>

        {/* Slide-in keyframes injected once per drawer mount. Scoped via the
            uncommon name to avoid clashing with global animations. */}
        <style>{`
          @keyframes ksp-audit-slide-in {
            from { transform: translateX(24px); opacity: 0; }
            to   { transform: translateX(0);    opacity: 1; }
          }
        `}</style>
      </aside>
    </div>
  );
}

export default AuditDrawer;
