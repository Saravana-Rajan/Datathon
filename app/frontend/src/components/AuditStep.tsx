"use client";

import * as React from "react";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  confidenceStatus,
  formatConfidence,
  formatLatency,
  getStatusTheme,
  getStepIcon,
  stepHeadline,
} from "@/lib/audit-format";
import type {
  AuditInputStep,
  AuditIntentStep,
  AuditLanguageStep,
  AuditOutputStep,
  AuditStep as AuditStepType,
  AuditSynthesizerStep,
  AuditToolStep,
} from "@/types/audit";

import { AuditCodeBlock } from "./AuditCodeBlock";

// ---------------------------------------------------------------------------
// Sub-renderers per step type. Each one returns the *body* of the step
// (the part that appears below the headline when expanded).
// ---------------------------------------------------------------------------
function InputBody({ step }: { step: AuditInputStep }): JSX.Element {
  return (
    <div className="space-y-2">
      <DetailRow label="Channel">
        <span className="capitalize">{step.channel}</span>
      </DetailRow>
      {step.role ? <DetailRow label="Role">{step.role}</DetailRow> : null}
      <QuoteBlock label="Raw query" lang={step.rawQuery.length > 0 ? undefined : undefined}>
        {step.rawQuery}
      </QuoteBlock>
      {step.translatedQuery ? (
        <QuoteBlock label="Translation">{step.translatedQuery}</QuoteBlock>
      ) : null}
    </div>
  );
}

function LanguageBody({ step }: { step: AuditLanguageStep }): JSX.Element {
  return (
    <div className="space-y-2">
      <DetailRow label="Detected">
        <code className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono">
          {step.detected}
        </code>
      </DetailRow>
      <DetailRow label="Confidence">
        <ConfidenceBar value={step.confidence} />
      </DetailRow>
      {step.script ? <DetailRow label="Script">{step.script}</DetailRow> : null}
      {step.detector ? <DetailRow label="Detector">{step.detector}</DetailRow> : null}
    </div>
  );
}

function IntentBody({ step }: { step: AuditIntentStep }): JSX.Element {
  return (
    <div className="space-y-2">
      <DetailRow label="Intent">
        <code className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono">
          {step.intent}
        </code>
      </DetailRow>
      <DetailRow label="Model">{step.model}</DetailRow>
      <DetailRow label="Confidence">
        <ConfidenceBar value={step.confidence} />
      </DetailRow>
      {step.toolPlan.length > 0 ? (
        <DetailRow label="Tool plan">
          <div className="flex flex-wrap gap-1">
            {step.toolPlan.map((t, i) => (
              <React.Fragment key={`${t}-${i}`}>
                <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-mono">
                  {t}
                </span>
                {i < step.toolPlan.length - 1 ? (
                  <ChevronRight
                    className="h-3.5 w-3.5 self-center text-muted-foreground"
                    aria-hidden="true"
                  />
                ) : null}
              </React.Fragment>
            ))}
          </div>
        </DetailRow>
      ) : null}
      {step.entities && Object.keys(step.entities).length > 0 ? (
        <DetailRow label="Entities">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-[12px]">
            {Object.entries(step.entities).map(([k, v]) => (
              <React.Fragment key={k}>
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono">{JSON.stringify(v)}</dd>
              </React.Fragment>
            ))}
          </dl>
        </DetailRow>
      ) : null}
    </div>
  );
}

function ToolBody({ step }: { step: AuditToolStep }): JSX.Element {
  switch (step.payload.kind) {
    case "sql": {
      const { query, rowCount, executionMs, preview } = step.payload.data;
      return (
        <div className="space-y-2">
          <AuditCodeBlock
            code={query}
            language="sql"
            label="SQL"
            trailing={
              <>
                {rowCount} row{rowCount === 1 ? "" : "s"} · {formatLatency(executionMs)}
              </>
            }
          />
          {preview && preview.length > 0 ? (
            <PreviewTable rows={preview} />
          ) : null}
        </div>
      );
    }
    case "cypher": {
      const { query, nodeCount, edgeCount, executionMs } = step.payload.data;
      return (
        <AuditCodeBlock
          code={query}
          language="cypher"
          label="Cypher"
          trailing={
            <>
              {nodeCount} nodes · {edgeCount} edges · {formatLatency(executionMs)}
            </>
          }
        />
      );
    }
    case "rag": {
      const { topK, passages, embedder } = step.payload.data;
      return (
        <div className="space-y-2">
          <DetailRow label="Embedder">{embedder}</DetailRow>
          <DetailRow label="Top-K">{topK}</DetailRow>
          <ul className="space-y-1.5">
            {passages.map((p, i) => (
              <li
                key={`${p.source}-${i}`}
                className="rounded-md border border-border bg-muted/40 p-2"
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-[11px] text-muted-foreground">
                    {p.source}
                  </span>
                  <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
                    sim {formatConfidence(p.similarity)}
                  </span>
                </div>
                <p className="line-clamp-3 text-[12px] leading-relaxed text-foreground/90">
                  {p.snippet}
                </p>
              </li>
            ))}
          </ul>
        </div>
      );
    }
    case "predictive": {
      const { model, forecast, features, confidence, excludedFeatures } =
        step.payload.data;
      return (
        <div className="space-y-2">
          <DetailRow label="Model">{model}</DetailRow>
          <DetailRow label="Confidence">
            <ConfidenceBar value={confidence} />
          </DetailRow>
          <DetailRow label="Features">
            <div className="flex flex-wrap gap-1">
              {features.map((f) => (
                <span
                  key={f}
                  className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-mono"
                >
                  {f}
                </span>
              ))}
            </div>
          </DetailRow>
          {excludedFeatures && excludedFeatures.length > 0 ? (
            <DetailRow label="Excluded (bias-safe)">
              <div className="flex flex-wrap gap-1">
                {excludedFeatures.map((f) => (
                  <span
                    key={f}
                    className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-mono text-rose-600 dark:text-rose-300"
                  >
                    ✕ {f}
                  </span>
                ))}
              </div>
            </DetailRow>
          ) : null}
          <DetailRow label="Forecast">
            <ul className="space-y-1">
              {forecast.map((f, i) => (
                <li
                  key={`${f.label}-${i}`}
                  className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1 text-[12px]"
                >
                  <span className="font-medium">{f.label}</span>
                  <span className="font-mono">
                    {f.value}
                    {f.ciLow !== undefined && f.ciHigh !== undefined ? (
                      <span className="ml-1 text-muted-foreground">
                        ({f.ciLow}–{f.ciHigh})
                      </span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </DetailRow>
        </div>
      );
    }
    case "raw":
    default:
      return (
        <AuditCodeBlock
          code={JSON.stringify(step.payload.data, null, 2)}
          language="json"
          label="JSON"
        />
      );
  }
}

function SynthesizerBody({ step }: { step: AuditSynthesizerStep }): JSX.Element {
  return (
    <div className="space-y-2">
      <DetailRow label="Model">
        <span className="font-medium">{step.model}</span>
      </DetailRow>
      <DetailRow label="Prompt tokens">{step.promptTokens.toLocaleString()}</DetailRow>
      <DetailRow label="Completion tokens">
        {step.completionTokens.toLocaleString()}
      </DetailRow>
      {step.rationale ? (
        <DetailRow label="Why this model">{step.rationale}</DetailRow>
      ) : null}
    </div>
  );
}

function OutputBody({ step }: { step: AuditOutputStep }): JSX.Element {
  const vizBadges: string[] = [];
  if (step.vizSpec?.map) vizBadges.push("map");
  if (step.vizSpec?.graph) vizBadges.push("graph");
  if (step.vizSpec?.chart) vizBadges.push(`chart: ${step.vizSpec.chart}`);

  return (
    <div className="space-y-2">
      <QuoteBlock label="Final answer">{step.answer}</QuoteBlock>
      <DetailRow label="Round-trip">
        <span className="font-mono">{formatLatency(step.totalRoundTripMs)}</span>
      </DetailRow>
      {vizBadges.length > 0 ? (
        <DetailRow label="Viz">
          <div className="flex flex-wrap gap-1">
            {vizBadges.map((b) => (
              <span
                key={b}
                className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
              >
                {b}
              </span>
            ))}
          </div>
        </DetailRow>
      ) : null}
      {step.citations && step.citations.length > 0 ? (
        <DetailRow label="Citations">
          <ul className="space-y-1">
            {step.citations.map((c, i) => (
              <li
                key={`${c.source}-${i}`}
                className="rounded border border-border bg-muted/40 px-2 py-1 text-[12px]"
              >
                <div className="font-mono text-[11px] text-muted-foreground">
                  {c.source}
                </div>
                {c.snippet ? (
                  <div className="line-clamp-2">{c.snippet}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </DetailRow>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-0.5 sm:grid sm:grid-cols-[max-content_1fr] sm:gap-x-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-[13px] text-foreground/90">{children}</div>
    </div>
  );
}

function QuoteBlock({
  label,
  children,
}: {
  label?: string;
  children: React.ReactNode;
  lang?: string;
}): JSX.Element {
  return (
    <div className="space-y-1">
      {label ? (
        <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
      ) : null}
      <blockquote className="rounded-md border-l-2 border-primary/50 bg-muted/40 px-3 py-2 text-[13px] leading-relaxed text-foreground/90">
        {children}
      </blockquote>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }): JSX.Element {
  const status = confidenceStatus(value);
  const theme = getStatusTheme(status);
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-24 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div
          className={cn("h-full rounded-full transition-all", theme.dot)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("font-mono text-[11px]", theme.text)}>
        {formatConfidence(value)}
      </span>
    </div>
  );
}

function PreviewTable({ rows }: { rows: Record<string, unknown>[] }): JSX.Element {
  const cols = React.useMemo(() => {
    const set = new Set<string>();
    rows.slice(0, 5).forEach((r) => Object.keys(r).forEach((k) => set.add(k)));
    return Array.from(set);
  }, [rows]);
  if (cols.length === 0) return <></>;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-[11px]">
        <thead className="bg-muted/60">
          <tr>
            {cols.map((c) => (
              <th
                key={c}
                className="px-2 py-1 text-left font-medium text-muted-foreground"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 5).map((r, i) => (
            <tr key={i} className="border-t border-border">
              {cols.map((c) => (
                <td key={c} className="px-2 py-1 font-mono">
                  {String(r[c] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 5 ? (
        <div className="border-t border-border bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground">
          + {rows.length - 5} more row{rows.length - 5 === 1 ? "" : "s"} (truncated for display)
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main step component — the collapsible card on the timeline.
// ---------------------------------------------------------------------------
export interface AuditStepProps {
  step: AuditStepType;
  index: number;
  defaultExpanded?: boolean;
}

export function AuditStep({
  step,
  index,
  defaultExpanded = false,
}: AuditStepProps): JSX.Element {
  const [expanded, setExpanded] = React.useState(defaultExpanded);
  const theme = getStatusTheme(step.status);
  const Icon = getStepIcon(step);

  const id = `audit-step-${index}-${step.id}`;
  const panelId = `${id}-panel`;

  return (
    <li
      data-audit-step
      className={cn(
        "relative pl-10",
        // Per-step left accent so colour cascades from dot → card.
      )}
    >
      {/* Dot on the spine */}
      <span
        aria-hidden="true"
        className={cn(
          "absolute left-[10px] top-3 flex h-3 w-3 items-center justify-center rounded-full ring-4 ring-background",
          theme.dot,
        )}
      />

      <div
        className={cn(
          "overflow-hidden rounded-lg border bg-card shadow-sm transition-shadow",
          theme.border,
          expanded && "shadow-md",
        )}
      >
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-controls={panelId}
          id={id}
          className={cn(
            "flex w-full items-start gap-3 px-3 py-2.5 text-left",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "hover:bg-muted/40",
          )}
        >
          <span
            className={cn(
              "mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
              "bg-muted text-foreground/80",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </span>

          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Step {index + 1}
              </span>
              <span className="font-medium text-foreground">{step.title}</span>
              <span
                className={cn(
                  "ml-auto rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                  theme.badge,
                )}
              >
                {formatLatency(step.latencyMs)}
              </span>
            </span>
            <span className="truncate text-[12px] text-muted-foreground">
              {stepHeadline(step)}
            </span>
          </span>

          <ChevronRight
            className={cn(
              "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-90",
            )}
            aria-hidden="true"
          />
        </button>

        {expanded ? (
          <div
            id={panelId}
            role="region"
            aria-labelledby={id}
            className="border-t border-border/60 bg-background/60 px-3 py-3"
          >
            {step.note ? (
              <p className="mb-2 text-[12px] italic text-muted-foreground">
                {step.note}
              </p>
            ) : null}
            {step.type === "input" ? <InputBody step={step} /> : null}
            {step.type === "language" ? <LanguageBody step={step} /> : null}
            {step.type === "intent" ? <IntentBody step={step} /> : null}
            {step.type === "tool" ? <ToolBody step={step} /> : null}
            {step.type === "synthesizer" ? <SynthesizerBody step={step} /> : null}
            {step.type === "output" ? <OutputBody step={step} /> : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}

export default AuditStep;
