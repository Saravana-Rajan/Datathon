/**
 * Zia STT proxy — POST audio bytes, get a transcript back.
 *
 * The Catalyst Zia Speech-to-Text Function lives behind Catalyst's
 * Functions URL and accepts an audio blob + language hint. We don't
 * call it directly from the browser for three reasons:
 *
 *   1. Catalyst API keys must not be shipped to the client.
 *   2. Zia STT only supports English + Hindi (kn-IN goes through Gemini
 *      Live API instead — see useGeminiLive hook + design.md § 9). This
 *      route guards against accidental Kannada submissions.
 *   3. We attach the caller's role JWT here so the backend can log who
 *      transcribed what (audit trail completeness, § 11.3).
 *
 * Audio format: any browser MediaRecorder output (webm/opus, mp4/aac, etc.)
 * is forwarded as-is — Catalyst Zia normalizes server-side. Max body 25 MB.
 */

import type { NextRequest } from "next/server";

export const runtime = "nodejs"; // we need streaming binary bodies
// Static hosting on Catalyst Web Client Hosting doesn't run /api routes —
// these handlers exist so Next dev + Vercel preview can mirror the
// production proxy. In Catalyst production the same logic lives in
// functions/zia-stt-proxy and is hit directly from the browser.

const ZIA_STT_URL =
  process.env.CATALYST_ZIA_STT_URL ||
  (process.env.NEXT_PUBLIC_CATALYST_API
    ? `${process.env.NEXT_PUBLIC_CATALYST_API}/server/zia-stt`
    : "");

const ALLOWED_LANGS = new Set(["en-IN", "en-US", "hi-IN"]);
const MAX_BYTES = 25 * 1024 * 1024;

export async function POST(req: NextRequest) {
  if (!ZIA_STT_URL) {
    return jsonError(
      503,
      "Zia STT is not configured. Set CATALYST_ZIA_STT_URL or NEXT_PUBLIC_CATALYST_API."
    );
  }

  const lang = req.nextUrl.searchParams.get("lang") ?? "en-IN";
  if (!ALLOWED_LANGS.has(lang)) {
    return jsonError(
      400,
      `Unsupported language '${lang}'. Zia STT supports en-IN, en-US, hi-IN. ` +
        `For kn-IN use the Gemini Live API path (see useGeminiLive hook).`
    );
  }

  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (contentLength > MAX_BYTES) {
    return jsonError(413, "Audio payload exceeds 25 MB limit.");
  }

  const contentType =
    req.headers.get("content-type") ?? "application/octet-stream";

  // Pass through the raw stream — avoids buffering large audio in memory.
  const body = req.body;
  if (!body) {
    return jsonError(400, "Empty request body.");
  }

  const auth = req.headers.get("authorization") ?? "";

  try {
    const upstream = await fetch(`${ZIA_STT_URL}?lang=${encodeURIComponent(lang)}`, {
      method: "POST",
      headers: {
        "Content-Type": contentType,
        ...(auth ? { Authorization: auth } : {}),
      },
      body,
      // @ts-expect-error — Node fetch needs `duplex: "half"` for streamed bodies.
      duplex: "half",
    });

    const responseContentType =
      upstream.headers.get("content-type") ?? "application/json";

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": responseContentType,
        // Surface the request id so it can be cross-referenced in the
        // Catalyst audit log.
        "X-Yaksha-Trace-Id":
          upstream.headers.get("x-trace-id") ??
          crypto.randomUUID(),
      },
    });
  } catch (err) {
    return jsonError(
      502,
      `Zia STT upstream failed: ${(err as Error).message}`
    );
  }
}

function jsonError(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
