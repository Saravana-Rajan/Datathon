"use client";

import * as React from "react";
import { useChat } from "@ai-sdk/react";
import { ShieldCheck, Languages, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useKspStore } from "@/lib/store";
import { ChatMessage, type ChatMessageLike } from "./ChatMessage";
import { MessageInput } from "./MessageInput";
import { TypingIndicator } from "./TypingIndicator";

/**
 * Visualization spec emitted by the synthesizer alongside its prose. The
 * backend Circuit appends one of these (newline-prefixed) per assistant turn
 * so the frontend can update the Map / Network / Chart panels without making
 * a second roundtrip.
 *
 *   <<VIZ>>{"kind":"map","markers":[...],"requestId":"req_..."}<<END>>
 *
 * We extract them, hide the marker block from the rendered text, and push
 * them into the Zustand store where MapPanel / NetworkGraph subscribe.
 */
interface VizSpec {
  kind: "map" | "graph" | "chart" | "forecast";
  requestId?: string;
  markers?: Array<{
    id: string;
    lat: number;
    lng: number;
    label?: string;
    severity?: "low" | "medium" | "high";
  }>;
  nodes?: Array<{
    id: string;
    label: string;
    type?: "person" | "fir" | "location";
  }>;
  edges?: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
  }>;
  series?: Array<{ x: string | number; y: number; label?: string }>;
  confidence?: { low: number; high: number };
}

const VIZ_RE = /<<VIZ>>([\s\S]*?)<<END>>/g;

/**
 * Strip viz blocks from the visible content and return both the cleaned text
 * and the parsed specs. We tolerate malformed JSON: a bad block is dropped
 * rather than crashing the chat.
 */
function extractVizSpecs(raw: string): { clean: string; specs: VizSpec[] } {
  const specs: VizSpec[] = [];
  const clean = raw.replace(VIZ_RE, (_match, body: string) => {
    try {
      const parsed = JSON.parse(body) as VizSpec;
      specs.push(parsed);
    } catch (err) {
      console.warn("[ChatPanel] Failed to parse viz_spec block", err);
    }
    return "";
  });
  return { clean: clean.trim(), specs };
}

/**
 * Pull the request_id out of message annotations if the server attached one
 * via the AI SDK `data` channel. Falls back to scanning the raw text for a
 * leading `<<RID>>req_xxx<<END>>` marker (legacy path).
 */
function extractRequestId(message: ChatMessageLike): string | undefined {
  const annotations = (message as unknown as { annotations?: unknown[] })
    .annotations;
  if (Array.isArray(annotations)) {
    for (const a of annotations) {
      if (
        typeof a === "object" &&
        a !== null &&
        "requestId" in a &&
        typeof (a as { requestId: unknown }).requestId === "string"
      ) {
        return (a as { requestId: string }).requestId;
      }
    }
  }
  const m = /<<RID>>([^<]+)<<END>>/.exec(message.content);
  return m?.[1];
}

export interface ChatPanelProps {
  /** Override the streaming API endpoint. Defaults to /api/chat. */
  apiEndpoint?: string;
  className?: string;
}

/**
 * Main chat surface.
 *
 * Streaming: backed by Vercel AI SDK's `useChat` which manages SSE/chunk
 * streaming, optimistic updates, error retries, and abort.
 *
 * Side-effects per assistant message:
 *   1. Parse viz_spec blocks → push to Zustand → MapPanel/NetworkGraph
 *      animate in lockstep with the prose.
 *   2. Attach request_id → ChatMessage "Why?" button opens AuditDrawer.
 *
 * The visible message text never contains the viz blocks — they're stripped
 * before render. Streaming tokens are shown live with a blinking caret in
 * ChatMessage; the TypingIndicator only appears before the first token lands.
 */
export function ChatPanel({
  apiEndpoint = "/api/chat",
  className,
}: ChatPanelProps): JSX.Element {
  const language = useKspStore((s) => s.language);
  const role = useKspStore((s) => s.role);
  const sessionId = useKspStore((s) => s.sessionId);
  const setMapMarkers = useKspStore((s) => s.setMapMarkers);
  const setGraph = useKspStore((s) => s.setGraph);
  const appendAuditEntry = useKspStore((s) => s.appendAuditEntry);

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    error,
    setInput,
    append,
    stop,
  } = useChat({
    api: apiEndpoint,
    body: {
      sessionId,
      language,
      role,
    },
    onError: (err) => {
      // Surface in console; the inline error banner below shows the user.
      console.error("[ChatPanel] chat stream error", err);
    },
  });

  // Track which message ids we've already pushed to the viz store so streaming
  // re-renders don't double-fire side effects.
  const processedRef = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    for (const msg of messages) {
      if (msg.role !== "assistant") continue;
      if (processedRef.current.has(msg.id)) continue;
      // Only commit side effects once the stream for this message has
      // finalized (i.e. it's not the message currently being streamed).
      const isCurrentStreaming =
        isLoading && msg.id === messages[messages.length - 1]?.id;
      if (isCurrentStreaming) continue;

      const { specs } = extractVizSpecs(msg.content);
      const requestId = extractRequestId(msg);

      for (const spec of specs) {
        const rid = spec.requestId ?? requestId;
        switch (spec.kind) {
          case "map":
            if (spec.markers) {
              // Translate viz_spec severity → store intensity (0..1) so the
              // heatmap layer can render without remapping.
              const sevToIntensity = (
                sev?: "low" | "medium" | "high",
              ): number => (sev === "high" ? 1 : sev === "medium" ? 0.6 : 0.3);
              setMapMarkers(
                spec.markers.map((m) => ({
                  id: m.id,
                  lat: m.lat,
                  lng: m.lng,
                  label: m.label,
                  intensity: sevToIntensity(m.severity),
                })),
              );
            }
            break;
          case "graph":
            if (spec.nodes && spec.edges) {
              // Force-fit nodes to the store's expected GraphNode shape
              // (default any unrecognized node type to "person" so React
              // Flow has something to render).
              const normalizedNodes = spec.nodes.map((n) => ({
                id: n.id,
                label: n.label,
                type:
                  n.type === "person" ||
                  n.type === "fir" ||
                  n.type === "location"
                    ? n.type
                    : ("person" as const),
              }));
              const normalizedEdges = spec.edges.map((e) => ({
                id: e.id,
                source: e.source,
                target: e.target,
                label: e.label ?? "",
              }));
              setGraph(normalizedNodes, normalizedEdges);
            }
            break;
          case "chart":
          case "forecast":
            // Chart/forecast surface is owned by the predictive panel; we
            // emit a CustomEvent so the dashboard can hook into it without
            // expanding the global store contract here.
            if (typeof window !== "undefined") {
              window.dispatchEvent(
                new CustomEvent("ksp:viz-chart", {
                  detail: {
                    kind: spec.kind,
                    series: spec.series ?? [],
                    confidence: spec.confidence,
                    requestId: rid,
                  },
                }),
              );
            }
            break;
        }
        if (rid) {
          appendAuditEntry({
            requestId: rid,
            timestamp: new Date().toISOString(),
            intent: spec.kind,
            summary:
              spec.kind === "forecast"
                ? `Forecast with ${spec.series?.length ?? 0} points`
                : `${spec.kind} viz attached`,
          });
        }
      }
      processedRef.current.add(msg.id);
    }
  }, [
    messages,
    isLoading,
    setMapMarkers,
    setGraphData,
    setChartData,
    recordAuditEntry,
  ]);

  // Smooth-scroll the message list to the bottom when new content arrives.
  const listRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    // requestAnimationFrame avoids layout thrash mid-stream.
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    });
  }, [messages]);

  const sendSuggested = React.useCallback(
    (text: string) => {
      if (!text.trim()) return;
      void append({ role: "user", content: text });
      setInput("");
    },
    [append, setInput],
  );

  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator =
    isLoading &&
    (!lastMessage ||
      lastMessage.role === "user" ||
      lastMessage.content.length === 0);

  return (
    <Card className={cn("flex h-full flex-col overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b py-3">
        <div className="flex items-center gap-2">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary"
            aria-hidden="true"
          >
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Saathi</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {role ? `${role} session` : "Guest session"}
            </span>
          </div>
        </div>

        <div
          className="flex items-center gap-2 text-xs"
          aria-label="Active language"
        >
          <Languages
            className="h-3.5 w-3.5 text-muted-foreground"
            aria-hidden="true"
          />
          <span
            className={cn(
              "rounded-md border bg-card px-2 py-0.5 font-medium uppercase tracking-wide",
              language === "kn" && "text-primary",
            )}
          >
            {language === "kn" ? "ಕನ್ನಡ · KN" : "EN"}
          </span>
          {isLoading && (
            <button
              type="button"
              onClick={stop}
              className="rounded-md border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Stop generating response"
            >
              Stop
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden p-3">
        <div
          ref={listRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
          aria-label="Conversation history"
          className="flex flex-1 flex-col gap-3 overflow-y-auto pr-1"
        >
          <ul className="flex flex-col gap-3" role="list">
            {messages.length === 0 && (
              <li className="m-auto max-w-md py-8 text-center text-sm text-muted-foreground">
                <ShieldCheck
                  className="mx-auto mb-2 h-8 w-8 text-primary/60"
                  aria-hidden="true"
                />
                <p className="font-medium text-foreground">
                  {language === "kn"
                    ? "ನಮಸ್ಕಾರ. ಯಾವ ಮಾಹಿತಿ ಬೇಕು?"
                    : "Namaskara. What do you want to investigate?"}
                </p>
                <p className="mt-1 text-xs">
                  {language === "kn"
                    ? "ಧ್ವನಿ ಅಥವಾ ಪಠ್ಯದಿಂದ ಕೇಳಿ. ಪ್ರತಿ ಉತ್ತರಕ್ಕೂ ಪೂರ್ಣ ಆಡಿಟ್ ಲಭ್ಯ."
                    : "Ask by voice or text. Every answer carries a full audit trail."}
                </p>
              </li>
            )}

            {messages.map((m, i) => {
              const requestId = extractRequestId(m);
              const isStreamingMsg =
                isLoading && i === messages.length - 1 && m.role === "assistant";
              const displayed =
                m.role === "assistant"
                  ? extractVizSpecs(m.content).clean
                  : m.content;
              return (
                <li key={m.id} role="listitem">
                  <ChatMessage
                    message={{ ...m, content: displayed }}
                    isStreaming={isStreamingMsg}
                    requestId={requestId}
                  />
                </li>
              );
            })}

            {showTypingIndicator && (
              <li role="listitem" className="flex justify-start pl-9">
                <TypingIndicator
                  label={
                    language === "kn"
                      ? "ಸಾಥಿ ಯೋಚಿಸುತ್ತಿದೆ"
                      : "Saathi is thinking"
                  }
                />
              </li>
            )}
          </ul>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {language === "kn"
                  ? "ಸಂಪರ್ಕ ತೊಂದರೆ"
                  : "Connection error"}
              </p>
              <p className="opacity-80">
                {error.message ||
                  (language === "kn"
                    ? "ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸಿ."
                    : "Please try again.")}
              </p>
            </div>
          </div>
        )}

        <MessageInput
          value={input}
          onChange={handleInputChange}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onSendText={sendSuggested}
          showSuggestions={messages.length === 0}
        />
      </CardContent>
    </Card>
  );
}

export default ChatPanel;
