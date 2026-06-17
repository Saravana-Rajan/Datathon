"use client";

/**
 * Gemini Live API client — primary Kannada voice path for Sarvik.
 *
 * Gemini Live is a bidirectional WebSocket that accepts streaming PCM16 audio
 * frames and emits interleaved text + audio chunks back. We talk to it via
 * the Google GenAI Web SDK (`@google/genai`), loaded dynamically so the
 * Next.js server bundle stays slim.
 *
 * Auth note: in production the API key MUST be proxied via a Catalyst
 * Function so it never reaches the client. For the hackathon demo we read
 * `NEXT_PUBLIC_GEMINI_API_KEY` per spec — `app/backend/functions/gemini-live-proxy`
 * (planned, see plans/) will replace this transport later.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { float32ToPcm16, GEMINI_LIVE_SAMPLE_RATE } from "@/lib/audio";

export type GeminiConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "closing"
  | "closed"
  | "error";

export type GeminiLanguage = "kn" | "en" | "hi";

export interface UseGeminiLiveOptions {
  model?: string; // default "gemini-live-2.5-flash-preview"
  apiKey?: string; // overrides env var, useful for tests
  systemInstruction?: string;
  /** Auto-reconnect on unexpected close. Default true. */
  autoReconnect?: boolean;
  /** Max reconnect attempts before surfacing error. Default 5. */
  maxReconnectAttempts?: number;
}

export interface UseGeminiLiveReturn {
  state: GeminiConnectionState;
  error: string | null;
  connect: (language: GeminiLanguage) => Promise<void>;
  disconnect: () => Promise<void>;
  sendAudio: (chunk: Float32Array | ArrayBuffer) => void;
  sendText: (text: string) => void;
  onTextChunk: (cb: (chunk: string) => void) => () => void;
  onAudioChunk: (cb: (chunk: ArrayBuffer) => void) => () => void;
  onTurnComplete: (cb: () => void) => () => void;
  onTranscript: (cb: (transcript: string, isFinal: boolean) => void) => () => void;
}

const DEFAULT_MODEL = "gemini-live-2.5-flash-preview";
const LANG_INSTRUCTIONS: Record<GeminiLanguage, string> = {
  kn: "ನೀವು ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಸಹಾಯ ಮಾಡುವ AI ಸಹಾಯಕರು. ಯಾವಾಗಲೂ ಸ್ಪಷ್ಟ, ಸಂಕ್ಷಿಪ್ತ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.",
  en: "You are an AI assistant for Karnataka State Police investigators. Reply concisely.",
  hi: "आप कर्नाटक राज्य पुलिस जांचकर्ताओं के लिए AI सहायक हैं। संक्षिप्त उत्तर दें।",
};

// Structural typing of the slice of @google/genai we use, so we don't have to
// declare a dependency on its full type tree at import time.
interface GenAISession {
  sendRealtimeInput: (input: {
    audio?: { data: string; mimeType: string };
    text?: string;
  }) => void;
  sendClientContent?: (input: { turns: Array<{ role: string; parts: Array<{ text: string }> }>; turnComplete?: boolean }) => void;
  close: () => void;
}

interface LiveMessage {
  serverContent?: {
    modelTurn?: {
      parts?: Array<{
        text?: string;
        inlineData?: { data: string; mimeType: string };
      }>;
    };
    inputTranscription?: { text: string; finished?: boolean };
    outputTranscription?: { text: string; finished?: boolean };
    turnComplete?: boolean;
    interrupted?: boolean;
  };
  setupComplete?: object;
}

interface GenAILiveConfig {
  responseModalities?: string[];
  systemInstruction?: { parts: Array<{ text: string }> };
  inputAudioTranscription?: object;
  outputAudioTranscription?: object;
  speechConfig?: { languageCode?: string };
}

interface GenAILiveConnectArgs {
  model: string;
  config: GenAILiveConfig;
  callbacks: {
    onopen?: () => void;
    onmessage: (msg: LiveMessage) => void;
    onerror?: (err: Event | Error) => void;
    onclose?: (ev: CloseEvent | { reason?: string }) => void;
  };
}

interface GenAIClient {
  live: { connect: (args: GenAILiveConnectArgs) => Promise<GenAISession> };
}

interface GoogleGenAIModule {
  GoogleGenAI: new (opts: { apiKey: string }) => GenAIClient;
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  // Chunk to avoid call-stack overflow on large frames.
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(bytes.subarray(i, i + CHUNK)),
    );
  }
  return btoa(binary);
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out.buffer;
}

export function useGeminiLive(
  options: UseGeminiLiveOptions = {},
): UseGeminiLiveReturn {
  const {
    model = DEFAULT_MODEL,
    apiKey = process.env.NEXT_PUBLIC_GEMINI_API_KEY,
    systemInstruction,
    autoReconnect = true,
    maxReconnectAttempts = 5,
  } = options;

  const [state, setState] = useState<GeminiConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);

  const sessionRef = useRef<GenAISession | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const lastLanguageRef = useRef<GeminiLanguage>("kn");
  const explicitCloseRef = useRef(false);

  const textCbsRef = useRef(new Set<(c: string) => void>());
  const audioCbsRef = useRef(new Set<(c: ArrayBuffer) => void>());
  const turnCbsRef = useRef(new Set<() => void>());
  const transcriptCbsRef = useRef(new Set<(t: string, f: boolean) => void>());

  const handleMessage = useCallback((msg: LiveMessage) => {
    const sc = msg.serverContent;
    if (!sc) return;

    if (sc.modelTurn?.parts) {
      for (const part of sc.modelTurn.parts) {
        if (part.text) {
          for (const cb of textCbsRef.current) cb(part.text);
        }
        if (part.inlineData?.data && part.inlineData.mimeType.startsWith("audio/")) {
          const ab = base64ToArrayBuffer(part.inlineData.data);
          for (const cb of audioCbsRef.current) cb(ab);
        }
      }
    }
    if (sc.outputTranscription?.text) {
      const finished = !!sc.outputTranscription.finished;
      for (const cb of transcriptCbsRef.current) {
        cb(sc.outputTranscription.text, finished);
      }
    }
    if (sc.turnComplete) {
      for (const cb of turnCbsRef.current) cb();
    }
  }, []);

  const doConnect = useCallback(
    async (language: GeminiLanguage): Promise<void> => {
      if (!apiKey) {
        const err = "NEXT_PUBLIC_GEMINI_API_KEY is not set";
        setError(err);
        setState("error");
        throw new Error(err);
      }
      lastLanguageRef.current = language;
      setState("connecting");
      setError(null);
      explicitCloseRef.current = false;

      try {
        const mod = (await import("@google/genai")) as unknown as GoogleGenAIModule;
        const client = new mod.GoogleGenAI({ apiKey });

        const langCode =
          language === "kn" ? "kn-IN" : language === "hi" ? "hi-IN" : "en-IN";
        const sysText = systemInstruction ?? LANG_INSTRUCTIONS[language];

        const session = await client.live.connect({
          model,
          config: {
            responseModalities: ["AUDIO"],
            systemInstruction: { parts: [{ text: sysText }] },
            inputAudioTranscription: {},
            outputAudioTranscription: {},
            speechConfig: { languageCode: langCode },
          },
          callbacks: {
            onopen: () => {
              setState("open");
              reconnectAttemptsRef.current = 0;
            },
            onmessage: handleMessage,
            onerror: (err) => {
              const msg = err instanceof Error ? err.message : "live socket error";
              setError(msg);
              setState("error");
            },
            onclose: () => {
              sessionRef.current = null;
              setState("closed");
              if (
                !explicitCloseRef.current &&
                autoReconnect &&
                reconnectAttemptsRef.current < maxReconnectAttempts
              ) {
                const attempt = reconnectAttemptsRef.current + 1;
                reconnectAttemptsRef.current = attempt;
                const backoff = Math.min(15_000, 250 * 2 ** attempt);
                setTimeout(() => {
                  void doConnect(lastLanguageRef.current);
                }, backoff);
              }
            },
          },
        });
        sessionRef.current = session;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setState("error");
        throw err;
      }
    },
    [
      apiKey,
      model,
      systemInstruction,
      autoReconnect,
      maxReconnectAttempts,
      handleMessage,
    ],
  );

  const connect = useCallback(
    (language: GeminiLanguage) => doConnect(language),
    [doConnect],
  );

  const disconnect = useCallback(async () => {
    explicitCloseRef.current = true;
    if (sessionRef.current) {
      setState("closing");
      try {
        sessionRef.current.close();
      } catch {
        /* ignore */
      }
      sessionRef.current = null;
    }
    setState("closed");
  }, []);

  const sendAudio = useCallback((chunk: Float32Array | ArrayBuffer) => {
    const session = sessionRef.current;
    if (!session) return;
    const pcm =
      chunk instanceof Float32Array ? float32ToPcm16(chunk) : chunk;
    const b64 = arrayBufferToBase64(pcm);
    session.sendRealtimeInput({
      audio: {
        data: b64,
        mimeType: `audio/pcm;rate=${GEMINI_LIVE_SAMPLE_RATE}`,
      },
    });
  }, []);

  const sendText = useCallback((text: string) => {
    const session = sessionRef.current;
    if (!session) return;
    if (session.sendClientContent) {
      session.sendClientContent({
        turns: [{ role: "user", parts: [{ text }] }],
        turnComplete: true,
      });
    } else {
      session.sendRealtimeInput({ text });
    }
  }, []);

  // Stable register/unregister helpers for the various event streams.
  const onTextChunk = useCallback((cb: (c: string) => void) => {
    textCbsRef.current.add(cb);
    return () => {
      textCbsRef.current.delete(cb);
    };
  }, []);
  const onAudioChunk = useCallback((cb: (c: ArrayBuffer) => void) => {
    audioCbsRef.current.add(cb);
    return () => {
      audioCbsRef.current.delete(cb);
    };
  }, []);
  const onTurnComplete = useCallback((cb: () => void) => {
    turnCbsRef.current.add(cb);
    return () => {
      turnCbsRef.current.delete(cb);
    };
  }, []);
  const onTranscript = useCallback(
    (cb: (t: string, f: boolean) => void) => {
      transcriptCbsRef.current.add(cb);
      return () => {
        transcriptCbsRef.current.delete(cb);
      };
    },
    [],
  );

  useEffect(() => {
    return () => {
      explicitCloseRef.current = true;
      if (sessionRef.current) {
        try {
          sessionRef.current.close();
        } catch {
          /* ignore */
        }
        sessionRef.current = null;
      }
    };
  }, []);

  return {
    state,
    error,
    connect,
    disconnect,
    sendAudio,
    sendText,
    onTextChunk,
    onAudioChunk,
    onTurnComplete,
    onTranscript,
  };
}
