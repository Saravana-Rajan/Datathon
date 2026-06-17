"use client";

import * as React from "react";
import { useChat } from "@ai-sdk/react";
import { ShieldCheck, Languages, AlertTriangle, Radio, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useKspStore, type Language } from "@/lib/store";
import { ChatMessage, type ChatMessageLike } from "./ChatMessage";
import { MessageInput } from "./MessageInput";
import { TypingIndicator } from "./TypingIndicator";
import { SuggestionCard, DEFAULT_SUGGESTIONS } from "./SuggestionCard";
import { VoiceModeOverlay } from "./VoiceModeOverlay";
import { SparkOrb } from "./SparkOrb";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import dynamic from "next/dynamic";

// Lazy load voice recorder to keep WASM out of SSR.
const VoiceRecorder = dynamic(
  () => import("./VoiceRecorder").then((m) => m.VoiceRecorder),
  { ssr: false },
);

/**
 * Detect at runtime whether Gemini Live is wired up. Two preconditions:
 *   1. `NEXT_PUBLIC_GEMINI_LIVE_API_KEY` (or the legacy `NEXT_PUBLIC_GEMINI_API_KEY`)
 *      is set at build time — Next inlines `NEXT_PUBLIC_*` vars into the static
 *      bundle. To enable, drop the key into `.env.local`:
 *
 *          NEXT_PUBLIC_GEMINI_LIVE_API_KEY=AQ.AbXXXXXXXX
 *
 *      DO NOT commit the value. For production we still need a Catalyst
 *      function to proxy the WebSocket so the key isn't shipped to clients.
 *   2. The `@google/genai` SDK must resolve. We intentionally don't add it as
 *      a dep — install it locally with `npm i @google/genai` to dev with the
 *      live path. If the import fails the chat panel falls back to webkit.
 */
const GEMINI_LIVE_API_KEY =
  process.env.NEXT_PUBLIC_GEMINI_LIVE_API_KEY ??
  process.env.NEXT_PUBLIC_GEMINI_API_KEY ??
  "";
const GEMINI_LIVE_AVAILABLE = GEMINI_LIVE_API_KEY.length > 0;

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
    setMessages,
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

  // ─── Demo-mode fallback ─────────────────────────────────────────────────
  // The orchestrator endpoint returns 500 (HTML) while the backend team is
  // still wiring it up. Rather than show a raw HTML error banner to judges,
  // we synthesize a believable streaming response with a viz_spec attached
  // so the map/network panels still light up. This is intentionally
  // permissive — it makes the demo bulletproof even if the backend is down.
  const replyToUserInDemoMode = React.useCallback(
    (userText: string) => {
      const lower = userText.toLowerCase();
      // Heuristic: pick a believable canned response by intent keywords.
      let reply: string;
      let viz:
        | {
            kind: "map" | "graph";
            markers?: Array<{
              id: string;
              lat: number;
              lng: number;
              label: string;
              severity: "low" | "medium" | "high";
            }>;
            nodes?: Array<{ id: string; label: string; type: "person" | "fir" | "location" }>;
            edges?: Array<{ id: string; source: string; target: string; label?: string }>;
          }
        | null = null;

      if (
        lower.includes("offender") ||
        lower.includes("indiranagar") ||
        lower.includes("network") ||
        lower.includes("ಅಪರಾಧಿ")
      ) {
        reply =
          language === "kn"
            ? "ಇಂದಿರಾನಗರ ಪ್ರದೇಶದಲ್ಲಿ ಕಳೆದ 90 ದಿನಗಳಲ್ಲಿ 7 ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳನ್ನು ಗುರುತಿಸಲಾಗಿದೆ. ಪ್ರಮುಖ ಗ್ಯಾಂಗ್ ಲೀಡರ್‌ಗಳು ಮತ್ತು ಸಹ-ಆರೋಪಿಗಳ ಜಾಲವನ್ನು ನೆಟ್‌ವರ್ಕ್ ಟ್ಯಾಬ್‌ನಲ್ಲಿ ತೋರಿಸಲಾಗಿದೆ."
            : "Identified 7 repeat offenders in the Indiranagar beat over the last 90 days. Top suspects: Ravi K., Manjunath S., and Yusuf B. Their co-accused network is now visualized in the Network tab.";
        viz = {
          kind: "graph",
          nodes: [
            { id: "p1", label: "Ravi K.", type: "person" },
            { id: "p2", label: "Manjunath S.", type: "person" },
            { id: "p3", label: "Yusuf B.", type: "person" },
            { id: "p4", label: "Anil M.", type: "person" },
            { id: "f1", label: "FIR 412/24", type: "fir" },
            { id: "f2", label: "FIR 198/24", type: "fir" },
          ],
          edges: [
            { id: "e1", source: "p1", target: "p2", label: "co-accused" },
            { id: "e2", source: "p2", target: "p3", label: "phone link" },
            { id: "e3", source: "p1", target: "f1", label: "accused in" },
            { id: "e4", source: "p3", target: "f2", label: "accused in" },
            { id: "e5", source: "p4", target: "p2", label: "vehicle link" },
          ],
        };
      } else if (
        lower.includes("hotspot") ||
        lower.includes("mg road") ||
        lower.includes("pattern") ||
        lower.includes("ಹಾಟ್‌ಸ್ಪಾಟ್")
      ) {
        reply =
          language === "kn"
            ? "ಎಂಜಿ ರಸ್ತೆ ಸುತ್ತಮುತ್ತಲ 3 ಸಕ್ರಿಯ ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳನ್ನು ನಕ್ಷೆಯಲ್ಲಿ ತೋರಿಸಲಾಗಿದೆ. ಮುಖ್ಯ ಮಾದರಿಗಳು: ರಾತ್ರಿ 10–2 ಗಂಟೆ ನಡುವೆ ಜೇಬುಗಳ್ಳತನ ಮತ್ತು ಎರಡು ಚಕ್ರ ವಾಹನ ಕಳ್ಳತನ."
            : "3 active hotspots clustered around MG Road. Dominant pattern: pickpocketing and two-wheeler theft between 22:00 and 02:00. Map updated.";
        viz = {
          kind: "map",
          markers: [
            { id: "h1", lat: 12.9756, lng: 77.6076, label: "MG Road hotspot", severity: "high" },
            { id: "h2", lat: 12.9745, lng: 77.6098, label: "Brigade Junction", severity: "medium" },
            { id: "h3", lat: 12.9712, lng: 77.6122, label: "Trinity Circle", severity: "low" },
          ],
        };
      } else {
        reply =
          language === "kn"
            ? "ಡೆಮೋ ಮೋಡ್: ಆರ್ಕೆಸ್ಟ್ರೇಟರ್ ಬ್ಯಾಕೆಂಡ್ ಸದ್ಯ ತಲುಪಲಾಗುತ್ತಿಲ್ಲ. ಮಾದರಿ ಪ್ರಶ್ನೆಗಳನ್ನು ಚಿಪ್‌ಗಳಿಂದ ಪ್ರಯತ್ನಿಸಿ — ಪೂರ್ಣ ಫ್ಲೋ ಲೈವ್ ಆದಾಗ ಅದೇ ಪ್ರಶ್ನೆಗಳು ರೂಟ್ ಆಗುತ್ತವೆ."
            : "Demo mode: the live orchestrator is currently unreachable. Try the suggestion chips for canned answers — once the backend is wired up, the same queries will route to the real pipeline.";
      }

      const requestId = `req_demo_${Date.now()}`;
      const vizBlock = viz
        ? `\n\n<<VIZ>>${JSON.stringify({ ...viz, requestId })}<<END>>`
        : "";
      const assistantContent = reply + vizBlock + `<<RID>>${requestId}<<END>>`;

      // Append the synthetic assistant message after a small delay so the
      // typing indicator gets a chance to flash.
      window.setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: `demo-${Date.now()}`,
            role: "assistant",
            content: assistantContent,
          } as (typeof prev)[number],
        ]);
      }, 420);
    },
    [language, setMessages]
  );

  // When the orchestrator errors out, automatically fall back to demo mode
  // for whatever the user last sent. We only fire ONCE per error/turn pair.
  const lastDemoFillRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!error) return;
    if (isLoading) return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    if (lastDemoFillRef.current === lastUser.id) return;
    const lastAssistantId = messages[messages.length - 1]?.id;
    if (lastAssistantId && lastAssistantId !== lastUser.id) {
      // An assistant message already replied — don't double-fill.
      const lastAssistant = messages[messages.length - 1];
      if (lastAssistant.role === "assistant") return;
    }
    lastDemoFillRef.current = lastUser.id;
    replyToUserInDemoMode(lastUser.content);
  }, [error, isLoading, messages, replyToUserInDemoMode]);

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
  }, [messages, isLoading, setMapMarkers, setGraph, appendAuditEntry]);

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

  // ─── Voice input ────────────────────────────────────────────────────────
  // Two-path strategy:
  //   (A) Gemini Live voice-to-voice — bidirectional WebSocket streaming via
  //       the VoiceRecorder component, model `gemini-live-2.5-flash-preview`.
  //       Enabled when NEXT_PUBLIC_GEMINI_LIVE_API_KEY is present AND the user
  //       has flipped voice mode to "Live" (defaults ON for Kannada).
  //   (B) Browser `webkitSpeechRecognition` — zero-backend fallback that
  //       dictates into the text input. Always available as a safety net so
  //       the demo never breaks.
  //
  // TODO(prod): replace direct WS with a Catalyst function proxy at
  //   `/server/gemini-live-proxy` so we never ship the API key in the bundle.

  const [voiceMode, setVoiceMode] = React.useState<"live" | "dictation">(
    GEMINI_LIVE_AVAILABLE ? "live" : "dictation",
  );
  // If Gemini Live becomes unavailable mid-session (key cleared via devtools,
  // etc.), demote silently. Keeps the UI honest.
  React.useEffect(() => {
    if (!GEMINI_LIVE_AVAILABLE && voiceMode === "live") {
      setVoiceMode("dictation");
    }
  }, [voiceMode]);

  const [isLiveVoiceOpen, setIsLiveVoiceOpen] = React.useState(false);

  // Bridge Gemini Live transcripts into the chat history so the map/network
  // panels still light up via the existing viz_spec pipeline.
  const handleLiveTranscript = React.useCallback(
    (text: string, lang: Language) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      // Append as a user turn — the orchestrator will reply via SSE and the
      // viz_spec extractor below will pick up any markers.
      void append({ role: "user", content: trimmed });
      // Hint the store at the spoken language so prompts/UI follow suit.
      if (lang !== language) {
        useKspStore.getState().setLanguage(lang);
      }
    },
    [append, language],
  );

  const handleLiveResponse = React.useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      // Inject the spoken assistant turn into the chat history as a real
      // message so the audit trail + transcript scrollback stay coherent.
      const id = `gemini-live-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id,
          role: "assistant",
          content: trimmed,
        } as (typeof prev)[number],
      ]);
    },
    [setMessages],
  );

  type SRType = {
    new (): {
      lang: string;
      interimResults: boolean;
      continuous: boolean;
      onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
      onerror: (e: { error?: string }) => void;
      onend: () => void;
      start: () => void;
      stop: () => void;
    };
  };
  const recognitionRef = React.useRef<InstanceType<SRType> | null>(null);
  const [isRecording, setIsRecording] = React.useState(false);
  const [voiceError, setVoiceError] = React.useState<string | null>(null);

  const toggleVoice = React.useCallback(() => {
    setVoiceError(null);
    // Live mode → open the VoiceRecorder overlay (Gemini Live WebSocket).
    if (voiceMode === "live" && GEMINI_LIVE_AVAILABLE) {
      setIsLiveVoiceOpen((v) => !v);
      return;
    }
    if (typeof window === "undefined") return;
    const w = window as unknown as {
      SpeechRecognition?: SRType;
      webkitSpeechRecognition?: SRType;
    };
    const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!SR) {
      setVoiceError(
        language === "kn"
          ? "ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಧ್ವನಿ ಬೆಂಬಲಿಸುವುದಿಲ್ಲ. Chrome ಅಥವಾ Edge ಬಳಸಿ."
          : "Voice input is not supported in this browser. Try Chrome or Edge."
      );
      return;
    }
    if (isRecording) {
      recognitionRef.current?.stop();
      return;
    }
    try {
      const rec = new SR();
      rec.lang = language === "kn" ? "kn-IN" : "en-IN";
      rec.interimResults = true;
      rec.continuous = false;
      let finalText = "";
      rec.onresult = (e) => {
        let interim = "";
        let finalChunk = "";
        for (let i = 0; i < e.results.length; i++) {
          const res = e.results[i] as ArrayLike<{ transcript: string }> & {
            isFinal?: boolean;
          };
          const text = res[0]?.transcript ?? "";
          if (res.isFinal) finalChunk += text;
          else interim += text;
        }
        finalText = finalChunk || finalText;
        const display = (finalText + " " + interim).trim();
        setInput(display);
      };
      rec.onerror = (e) => {
        const code = e.error ?? "unknown";
        setVoiceError(
          code === "not-allowed" || code === "service-not-allowed"
            ? language === "kn"
              ? "ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಅನುಮತಿಸಿ."
              : "Microphone permission was blocked. Allow it in your browser site settings."
            : language === "kn"
              ? "ಧ್ವನಿ ಗುರುತಿಸುವಿಕೆಯಲ್ಲಿ ದೋಷ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."
              : "Speech recognition error. Please try again."
        );
        setIsRecording(false);
      };
      rec.onend = () => {
        setIsRecording(false);
        // Auto-send if we captured a non-trivial utterance.
        if (finalText.trim().length > 0) {
          void append({ role: "user", content: finalText.trim() });
          setInput("");
        }
      };
      recognitionRef.current = rec;
      rec.start();
      setIsRecording(true);
    } catch (err) {
      console.error("[ChatPanel] SpeechRecognition start failed", err);
      setIsRecording(false);
      setVoiceError(
        language === "kn"
          ? "ಮೈಕ್ರೊಫೋನ್ ಪ್ರಾರಂಭಿಸಲಾಗಲಿಲ್ಲ."
          : "Could not start the microphone."
      );
    }
  }, [append, isRecording, language, setInput, voiceMode]);

  React.useEffect(() => {
    // Stop any in-flight recognition if the panel unmounts.
    return () => {
      try {
        recognitionRef.current?.stop();
      } catch {
        // ignore
      }
    };
  }, []);

  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator =
    isLoading &&
    (!lastMessage ||
      lastMessage.role === "user" ||
      lastMessage.content.length === 0);

  return (
    <Card className={cn("flex h-full flex-col overflow-hidden rounded-2xl border-slate-200/70 bg-white shadow-[0_2px_20px_-8px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-white/5", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-slate-100 py-3 dark:border-white/5">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl text-white shadow-sm"
            style={{
              background:
                "linear-gradient(135deg, #7c5cfa 0%, #4f46e5 50%, #ec4899 100%)",
            }}
            aria-hidden="true"
          >
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Sarvik</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {role ? `${role} session` : "Guest session"}
            </span>
          </div>
        </div>

        <div
          className="flex items-center gap-2 text-xs"
          aria-label="Active language"
        >
          {GEMINI_LIVE_AVAILABLE && (
            <button
              type="button"
              onClick={() =>
                setVoiceMode((m) => (m === "live" ? "dictation" : "live"))
              }
              aria-pressed={voiceMode === "live"}
              title={
                voiceMode === "live"
                  ? "Gemini Live voice mode — bidirectional Kannada voice-to-voice"
                  : "Browser dictation mode — text-only speech recognition"
              }
              className={cn(
                "flex items-center gap-1 rounded-md border px-2 py-0.5 font-medium uppercase tracking-wide transition-colors",
                voiceMode === "live"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
                  : "bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              <Radio
                className={cn(
                  "h-3 w-3",
                  voiceMode === "live" && "animate-pulse",
                )}
                aria-hidden="true"
              />
              {voiceMode === "live" ? "Live" : "Dict"}
            </button>
          )}
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
              <li className="m-auto flex w-full max-w-2xl flex-col items-center px-2 py-6 text-center">
                <SparkOrb phase="idle" size={200} className="mb-6" />
                <p
                  className="chat-empty-title text-[22px] font-semibold tracking-tight text-slate-800 dark:text-white"
                  style={
                    language === "kn"
                      ? {
                          fontFamily:
                            '"Tiro Kannada", "Noto Sans Kannada", "Nirmala UI", system-ui, serif',
                        }
                      : { letterSpacing: "-0.02em" }
                  }
                >
                  {language === "kn"
                    ? "ನಮಸ್ಕಾರ. ಯಾವ ಮಾಹಿತಿ ಬೇಕು?"
                    : "Namaskara. What do you want to investigate?"}
                </p>
                <p className="mt-2 max-w-md text-[13px] text-slate-500 dark:text-slate-400">
                  {language === "kn"
                    ? "ಧ್ವನಿ ಅಥವಾ ಪಠ್ಯದಿಂದ ಕೇಳಿ. ಪ್ರತಿ ಉತ್ತರಕ್ಕೂ ಪೂರ್ಣ ಆಡಿಟ್."
                    : "Ask by voice or text. Every answer carries a full audit trail."}
                </p>

                {/* Slash-style suggestion chips */}
                <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                  {DEFAULT_SUGGESTIONS.slice(0, 5).map((s) => (
                    <button
                      key={s.title}
                      type="button"
                      onClick={() => sendSuggested(s.prompt)}
                      className="spark-chip group"
                    >
                      <span className="spark-chip-prefix">/</span>
                      <span className="truncate">{s.title}</span>
                    </button>
                  ))}
                </div>
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
                      : "Sarvik is thinking"
                  }
                />
              </li>
            )}
          </ul>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-amber-300/40 bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {language === "kn"
                  ? "ಡೆಮೋ ಮೋಡ್ ಸಕ್ರಿಯ"
                  : "Demo mode active"}
              </p>
              <p className="opacity-80">
                {language === "kn"
                  ? "ಲೈವ್ ಆರ್ಕೆಸ್ಟ್ರೇಟರ್ ತಲುಪಲಾಗುತ್ತಿಲ್ಲ — ಮಾದರಿ ಉತ್ತರಗಳನ್ನು ತೋರಿಸಲಾಗುತ್ತಿದೆ."
                  : "Live orchestrator is unreachable — showing canned answers so the demo keeps moving."}
              </p>
            </div>
          </div>
        )}

        {voiceError && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-amber-300/40 bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
            <span>{voiceError}</span>
          </div>
        )}

        {isLiveVoiceOpen && GEMINI_LIVE_AVAILABLE && (
          <div
            role="region"
            aria-label="Live voice conversation"
            className="relative flex flex-col items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3"
          >
            <button
              type="button"
              onClick={() => setIsLiveVoiceOpen(false)}
              className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Close live voice"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <p className="text-[10px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
              {language === "kn"
                ? "ಲೈವ್ ಧ್ವನಿ — Gemini Live"
                : "Live voice — Gemini Live"}
            </p>
            <VoiceRecorder
              language={language}
              onTranscript={handleLiveTranscript}
              onResponseComplete={handleLiveResponse}
            />
          </div>
        )}

        <MessageInput
          value={input}
          onChange={handleInputChange}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onSendText={sendSuggested}
          onToggleVoice={toggleVoice}
          isRecording={isRecording || isLiveVoiceOpen}
          showSuggestions={messages.length === 0}
        />
      </CardContent>
    </Card>
  );
}

export default ChatPanel;
