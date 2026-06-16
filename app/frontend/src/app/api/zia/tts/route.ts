/**
 * Zia TTS proxy — POST text + language, get audio bytes back.
 *
 * Mirrors the /api/zia/stt route. Catalyst Zia TTS supports en-IN and
 * hi-IN today. Kannada goes through Gemini Live API's native multimodal
 * path (see useGeminiLive). Forwarding through Next.js keeps the
 * Catalyst Function key off the client and gives us a single place to
 * enforce the language guard.
 *
 * Request:  POST /api/zia/tts?lang=en-IN&voice=female-1
 *           body: { "text": "..." }
 * Response: audio/mpeg (or audio/wav, whatever Zia returns) streamed back.
 */

import type { NextRequest } from "next/server";

export const runtime = "nodejs";

const ZIA_TTS_URL =
  process.env.CATALYST_ZIA_TTS_URL ||
  (process.env.NEXT_PUBLIC_CATALYST_API
    ? `${process.env.NEXT_PUBLIC_CATALYST_API}/server/zia-tts`
    : "");

const ALLOWED_LANGS = new Set(["en-IN", "en-US", "hi-IN"]);
const MAX_TEXT_CHARS = 5_000;

interface TtsRequestBody {
  text?: string;
  voice?: string;
  /** Optional pitch/rate hint for prosody-aware voices. */
  prosody?: { rate?: number; pitch?: number };
}

export async function POST(req: NextRequest) {
  if (!ZIA_TTS_URL) {
    return jsonError(
      503,
      "Zia TTS is not configured. Set CATALYST_ZIA_TTS_URL or NEXT_PUBLIC_CATALYST_API."
    );
  }

  const lang = req.nextUrl.searchParams.get("lang") ?? "en-IN";
  const voice = req.nextUrl.searchParams.get("voice") ?? undefined;

  if (!ALLOWED_LANGS.has(lang)) {
    return jsonError(
      400,
      `Unsupported language '${lang}'. Zia TTS supports en-IN, en-US, hi-IN. ` +
        `For kn-IN use the Gemini Live API path.`
    );
  }

  let body: TtsRequestBody;
  try {
    body = (await req.json()) as TtsRequestBody;
  } catch {
    return jsonError(400, "Body must be JSON.");
  }

  const text = (body.text ?? "").trim();
  if (!text) {
    return jsonError(400, "Missing required field 'text'.");
  }
  if (text.length > MAX_TEXT_CHARS) {
    return jsonError(
      413,
      `Text exceeds ${MAX_TEXT_CHARS} char limit; split into smaller chunks.`
    );
  }

  const auth = req.headers.get("authorization") ?? "";

  const qs = new URLSearchParams({ lang });
  if (voice) qs.set("voice", voice);

  try {
    const upstream = await fetch(`${ZIA_TTS_URL}?${qs.toString()}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/mpeg, audio/wav, application/octet-stream",
        ...(auth ? { Authorization: auth } : {}),
      },
      body: JSON.stringify({
        text,
        voice,
        prosody: body.prosody ?? undefined,
      }),
    });

    if (!upstream.ok) {
      const errBody = await safeReadText(upstream);
      return jsonError(
        upstream.status,
        `Zia TTS upstream failed (${upstream.status}): ${errBody.slice(0, 240)}`
      );
    }

    const responseContentType =
      upstream.headers.get("content-type") ?? "audio/mpeg";

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": responseContentType,
        "Cache-Control": "no-store",
        "X-Yaksha-Trace-Id":
          upstream.headers.get("x-trace-id") ?? crypto.randomUUID(),
      },
    });
  } catch (err) {
    return jsonError(
      502,
      `Zia TTS upstream failed: ${(err as Error).message}`
    );
  }
}

async function safeReadText(r: Response): Promise<string> {
  try {
    return await r.text();
  } catch {
    return "<unreadable body>";
  }
}

function jsonError(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
