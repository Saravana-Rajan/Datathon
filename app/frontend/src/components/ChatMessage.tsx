"use client";

import * as React from "react";
import { ShieldCheck, User, Copy, FileDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Structural type for the messages we render. Matches the shape produced by
 * `useChat` from `@ai-sdk/react` without binding to its exact export name —
 * the AI SDK has renamed `Message` between major versions, so we use a local
 * minimal contract instead.
 */
export interface ChatMessageLike {
  id: string;
  /**
   * We widen to `string` so structural assignment from `useChat()` messages
   * (whose `role` union has grown over SDK versions to include `tool`, etc.)
   * always succeeds. Only `user` triggers the user-side branch; everything
   * else renders as an assistant bubble.
   */
  role: string;
  content: string;
  createdAt?: Date | string | number;
}

/**
 * Detect whether a message contains Kannada script so we can swap in a
 * Kannada-friendly font fallback. Range U+0C80–U+0CFF is the Kannada block.
 */
function hasKannada(text: string): boolean {
  return /[ಀ-೿]/.test(text);
}

/**
 * Tiny markdown subset renderer. We avoid pulling react-markdown into the
 * critical path (bundle weight, peer-dep churn) and instead handle the
 * structures the synthesizer actually emits: paragraphs, **bold**, *italic*,
 * `code`, lists, and inline citations [1][2].
 *
 * Citations render as clickable chips that open the audit drawer scoped to
 * the source index for the message's request_id.
 */
function renderInline(
  text: string,
  requestId: string | undefined,
  onCitationClick: (requestId: string, index: number) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Token order matters: citations first (they look like [1]), then bold,
  // italic, code. We use a single regex with alternation and walk the matches.
  const pattern =
    /(\[(\d+)\])|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(`([^`]+)`)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
    }
    if (match[1] !== undefined && match[2] !== undefined) {
      const idx = Number(match[2]);
      nodes.push(
        <button
          key={`c-${key++}`}
          type="button"
          onClick={() => {
            if (requestId) onCitationClick(requestId, idx);
          }}
          className="citation-enter mx-0.5 inline-flex h-4 min-w-[1.125rem] items-center justify-center rounded-full bg-violet-100 px-1.5 align-middle text-[10px] font-semibold text-[#7c5cfa] hover:bg-violet-200 focus:outline-none focus:ring-2 focus:ring-[#7c5cfa]/30 dark:bg-violet-500/15 dark:text-violet-300"
          aria-label={`Open citation ${idx} in audit trail`}
        >
          {idx}
        </button>,
      );
    } else if (match[3] !== undefined) {
      nodes.push(
        <strong key={`b-${key++}`} className="font-semibold">
          {match[4]}
        </strong>,
      );
    } else if (match[5] !== undefined) {
      nodes.push(
        <em key={`i-${key++}`} className="italic">
          {match[6]}
        </em>,
      );
    } else if (match[7] !== undefined) {
      nodes.push(
        <code
          key={`code-${key++}`}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
        >
          {match[8]}
        </code>,
      );
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}

function renderBlocks(
  text: string,
  requestId: string | undefined,
  onCitationClick: (requestId: string, index: number) => void,
): React.ReactNode {
  // Split on blank lines for paragraphs; bullet/numbered lists handled inline.
  const blocks = text.split(/\n{2,}/);
  return blocks.map((block, bi) => {
    const lines = block.split("\n");
    const isBullet = lines.every((ln) => /^\s*[-*]\s+/.test(ln));
    const isNumbered = lines.every((ln) => /^\s*\d+\.\s+/.test(ln));

    if (isBullet && lines.length > 1) {
      return (
        <ul key={bi} className="my-1 list-disc pl-5">
          {lines.map((ln, i) => (
            <li key={i}>
              {renderInline(
                ln.replace(/^\s*[-*]\s+/, ""),
                requestId,
                onCitationClick,
              )}
            </li>
          ))}
        </ul>
      );
    }
    if (isNumbered && lines.length > 1) {
      return (
        <ol key={bi} className="my-1 list-decimal pl-5">
          {lines.map((ln, i) => (
            <li key={i}>
              {renderInline(
                ln.replace(/^\s*\d+\.\s+/, ""),
                requestId,
                onCitationClick,
              )}
            </li>
          ))}
        </ol>
      );
    }
    return (
      <p key={bi} className="my-1 whitespace-pre-wrap leading-relaxed">
        {renderInline(block, requestId, onCitationClick)}
      </p>
    );
  });
}

export interface ChatMessageProps {
  message: ChatMessageLike;
  /** True while this message is still being streamed in. */
  isStreaming?: boolean;
  /** Optional request_id attached to the assistant message for audit lookup. */
  requestId?: string;
}

/**
 * A single chat bubble. User messages anchor right; assistant messages anchor
 * left with the KSP shield avatar. Long-press on touch or right-click on
 * desktop opens a small action menu (copy text, save as PDF). On assistant
 * messages, inline [1][2] citations open the audit drawer to the matching
 * source.
 */
export function ChatMessage({
  message,
  isStreaming = false,
  requestId,
}: ChatMessageProps): JSX.Element {
  const isUser = message.role === "user";
  const text = message.content;
  const kannada = hasKannada(text);
  // The audit drawer lives in the parent page. We dispatch a DOM event
  // instead of holding a setter so this component stays decoupled from the
  // page's drawer wiring (the page may swap Radix Drawer for Sheet later).
  const openAuditDrawer = React.useCallback((rid: string) => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent("ksp:open-audit", { detail: { requestId: rid } }),
    );
  }, []);

  const [menuOpen, setMenuOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const bubbleRef = React.useRef<HTMLDivElement | null>(null);

  // Dismiss the action menu on outside click.
  React.useEffect(() => {
    if (!menuOpen) return;
    function onDocClick(e: MouseEvent) {
      if (
        bubbleRef.current &&
        !bubbleRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [menuOpen]);

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Clipboard write failed", err);
    }
    setMenuOpen(false);
  }, [text]);

  const handleSavePdf = React.useCallback(() => {
    // Defer to the page-level PDF export; this just opens the audit drawer
    // so the user can confirm the turn they want exported. Full per-message
    // PDF is wired through /lib/api by the parent toolbar.
    if (requestId) openAuditDrawer(requestId);
    setMenuOpen(false);
  }, [requestId, openAuditDrawer]);

  const handleCitation = React.useCallback(
    (rid: string, _idx: number) => {
      // We surface the audit drawer scoped to the assistant turn. The drawer
      // itself highlights the matching source[index].
      openAuditDrawer(rid);
    },
    [openAuditDrawer],
  );

  // Long-press = 500 ms touch hold (mirrors native iOS/Android copy gesture).
  const longPressTimer = React.useRef<number | null>(null);
  const startLongPress = React.useCallback(() => {
    longPressTimer.current = window.setTimeout(() => setMenuOpen(true), 500);
  }, []);
  const cancelLongPress = React.useCallback(() => {
    if (longPressTimer.current !== null) {
      window.clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const onContextMenu = React.useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(true);
  }, []);

  return (
    <div
      className={cn(
        "flex w-full gap-2",
        isUser ? "justify-end" : "justify-start",
      )}
      role="listitem"
      aria-label={isUser ? "Your message" : "Sarvik response"}
    >
      {!isUser && (
        <div
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow-sm"
          style={{
            background:
              "linear-gradient(135deg, #7c5cfa 0%, #4f46e5 50%, #ec4899 100%)",
          }}
          aria-hidden="true"
        >
          <ShieldCheck className="h-3.5 w-3.5" />
        </div>
      )}

      <div
        ref={bubbleRef}
        onContextMenu={onContextMenu}
        onTouchStart={startLongPress}
        onTouchEnd={cancelLongPress}
        onTouchCancel={cancelLongPress}
        onTouchMove={cancelLongPress}
        className={cn(
          "chat-message-enter group relative max-w-[88%] sm:max-w-[82%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed transition-colors",
          isUser
            ? "rounded-br-md bg-white text-slate-800 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.10)] ring-1 ring-slate-200/80"
            : "rounded-bl-md bg-[#F1F1F4] text-slate-800 dark:bg-white/8 dark:text-slate-100",
          kannada && "font-kannada",
        )}
        style={
          kannada
            ? {
                fontFamily:
                  '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, sans-serif',
              }
            : undefined
        }
      >
        <div className="space-y-1">
          {isUser ? (
            <p className="whitespace-pre-wrap leading-relaxed">{text}</p>
          ) : (
            renderBlocks(text, requestId, handleCitation)
          )}
          {isStreaming && (
            <span
              aria-hidden="true"
              className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-current align-middle opacity-70"
            />
          )}
        </div>

        <div
          className={cn(
            "mt-1 flex items-center gap-1.5 text-[10px] opacity-70",
            isUser ? "justify-end" : "justify-start",
          )}
        >
          <time dateTime={message.createdAt?.toString()}>
            {message.createdAt
              ? new Date(message.createdAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : ""}
          </time>
          {!isUser && requestId && (
            <button
              type="button"
              onClick={() => openAuditDrawer(requestId)}
              className="ml-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Show audit trail for this response"
            >
              Why?
            </button>
          )}
        </div>

        {menuOpen && (
          <div
            role="menu"
            className="absolute right-0 top-full z-20 mt-1 flex min-w-[140px] flex-col rounded-md border bg-popover p-1 text-xs text-popover-foreground shadow-md"
          >
            <button
              role="menuitem"
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-muted focus:bg-muted focus:outline-none"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Copy className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span>{copied ? "Copied" : "Copy text"}</span>
            </button>
            {!isUser && requestId && (
              <button
                role="menuitem"
                type="button"
                onClick={handleSavePdf}
                className="flex items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-muted focus:bg-muted focus:outline-none"
              >
                <FileDown className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Save to PDF</span>
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-semibold text-slate-700 shadow-sm dark:bg-white/10 dark:text-slate-200"
          aria-hidden="true"
        >
          <User className="h-3.5 w-3.5" />
        </div>
      )}
    </div>
  );
}

export default ChatMessage;
