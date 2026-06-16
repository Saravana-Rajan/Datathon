"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Lightweight syntax-highlighted code block for SQL / Cypher / JSON.
 *
 * We deliberately avoid pulling in `react-syntax-highlighter` or `shiki` —
 * the bundle hit isn't worth it for the handful of tokens we actually
 * render. A tiny token-class regex set is enough to make queries readable
 * in the audit drawer, and it keeps the static bundle slim (Catalyst Web
 * Client Hosting is a static export, see design.md §6.1).
 *
 * Languages supported: sql, cypher, json. Anything else falls through as
 * plain text inside a monospaced frame.
 */
export type AuditCodeLanguage = "sql" | "cypher" | "json" | "text";

interface TokenRule {
  className: string;
  pattern: RegExp;
}

// Order matters — earlier rules win. Strings/comments must come first so
// keyword matchers inside string literals don't get re-styled.
const COMMON_RULES: TokenRule[] = [
  { className: "text-emerald-500", pattern: /--[^\n]*/g }, // SQL/Cypher line comment
  { className: "text-emerald-500", pattern: /\/\*[\s\S]*?\*\//g }, // block comment
  { className: "text-amber-500", pattern: /'(?:\\.|[^'\\])*'/g }, // single-quoted strings
  { className: "text-amber-500", pattern: /"(?:\\.|[^"\\])*"/g }, // double-quoted strings
  { className: "text-sky-400", pattern: /\b\d+(?:\.\d+)?\b/g }, // numbers
];

const SQL_KEYWORDS = [
  "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL",
  "ORDER", "BY", "GROUP", "HAVING", "LIMIT", "OFFSET", "JOIN", "INNER",
  "LEFT", "RIGHT", "OUTER", "ON", "AS", "DISTINCT", "COUNT", "SUM", "AVG",
  "MIN", "MAX", "BETWEEN", "LIKE", "CASE", "WHEN", "THEN", "ELSE", "END",
  "WITH", "UNION", "ALL", "INSERT", "UPDATE", "DELETE", "VALUES", "SET",
  "DESC", "ASC",
];
const CYPHER_KEYWORDS = [
  "MATCH", "RETURN", "WHERE", "WITH", "OPTIONAL", "CREATE", "MERGE",
  "DELETE", "DETACH", "SET", "ORDER", "BY", "LIMIT", "SKIP", "AS", "AND",
  "OR", "NOT", "IN", "IS", "NULL", "CALL", "YIELD", "UNWIND", "COUNT",
  "COLLECT", "DISTINCT", "DESC", "ASC",
];

function buildKeywordRule(words: string[]): TokenRule {
  return {
    className: "text-indigo-400 font-semibold",
    pattern: new RegExp(`\\b(?:${words.join("|")})\\b`, "gi"),
  };
}

const RULES_BY_LANG: Record<AuditCodeLanguage, TokenRule[]> = {
  sql: [...COMMON_RULES, buildKeywordRule(SQL_KEYWORDS)],
  cypher: [...COMMON_RULES, buildKeywordRule(CYPHER_KEYWORDS)],
  json: [
    { className: "text-amber-500", pattern: /"(?:\\.|[^"\\])*"(?=\s*:)/g }, // keys
    { className: "text-emerald-400", pattern: /"(?:\\.|[^"\\])*"/g }, // string values
    { className: "text-sky-400", pattern: /\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g },
    { className: "text-rose-400 font-semibold", pattern: /\b(?:true|false|null)\b/g },
  ],
  text: [],
};

interface Segment {
  text: string;
  className?: string;
}

/**
 * Tokenize `code` into non-overlapping coloured segments. We do a single
 * pass that picks the earliest match across all rules at each cursor
 * position — a classic "longest first wins" tokenizer.
 */
function tokenize(code: string, lang: AuditCodeLanguage): Segment[] {
  const rules = RULES_BY_LANG[lang];
  if (rules.length === 0) return [{ text: code }];

  type Hit = { index: number; length: number; className: string };
  const hits: Hit[] = [];

  for (const rule of rules) {
    const re = new RegExp(rule.pattern.source, rule.pattern.flags);
    let m: RegExpExecArray | null;
    while ((m = re.exec(code)) !== null) {
      hits.push({ index: m.index, length: m[0].length, className: rule.className });
      if (m[0].length === 0) re.lastIndex++; // guard zero-width
    }
  }

  hits.sort((a, b) => (a.index === b.index ? b.length - a.length : a.index - b.index));

  const segments: Segment[] = [];
  let cursor = 0;
  for (const hit of hits) {
    if (hit.index < cursor) continue; // overlap — already covered
    if (hit.index > cursor) {
      segments.push({ text: code.slice(cursor, hit.index) });
    }
    segments.push({
      text: code.slice(hit.index, hit.index + hit.length),
      className: hit.className,
    });
    cursor = hit.index + hit.length;
  }
  if (cursor < code.length) segments.push({ text: code.slice(cursor) });
  return segments;
}

export interface AuditCodeBlockProps {
  code: string;
  language?: AuditCodeLanguage;
  /** Label shown in the header (e.g. "SQL", "Cypher"). Defaults to language. */
  label?: string;
  /** Right-hand badge — usually row count / node count. */
  trailing?: React.ReactNode;
  maxHeightClass?: string;
  className?: string;
}

export function AuditCodeBlock({
  code,
  language = "text",
  label,
  trailing,
  maxHeightClass = "max-h-64",
  className,
}: AuditCodeBlockProps): JSX.Element {
  const [copied, setCopied] = React.useState(false);
  const segments = React.useMemo(() => tokenize(code, language), [code, language]);

  const handleCopy = React.useCallback(async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }
    } catch {
      // Clipboard may be unavailable in headless / insecure contexts — fail silently.
    }
  }, [code]);

  return (
    <div
      className={cn(
        "group rounded-md border border-border bg-slate-950/95 text-slate-100 shadow-inner",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-white/5 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
            {label ?? language}
          </span>
          {trailing ? (
            <span className="text-[10px] text-slate-500">· {trailing}</span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium",
            "text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-200",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/30",
          )}
          aria-label={`Copy ${label ?? language} to clipboard`}
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" aria-hidden="true" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" aria-hidden="true" />
              Copy
            </>
          )}
        </button>
      </div>
      <pre
        className={cn(
          "overflow-auto px-3 py-2 font-mono text-[12px] leading-relaxed",
          maxHeightClass,
        )}
      >
        <code>
          {segments.map((seg, i) =>
            seg.className ? (
              <span key={i} className={seg.className}>
                {seg.text}
              </span>
            ) : (
              <React.Fragment key={i}>{seg.text}</React.Fragment>
            ),
          )}
        </code>
      </pre>
    </div>
  );
}

export default AuditCodeBlock;
