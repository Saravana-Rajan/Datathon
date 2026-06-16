# Gemini Live API — Reference for KSP Saathi (Kannada Voice)

> **Project:** Datathon 2026 — Karnataka State Police "Saathi" bilingual voice
> investigator assistant.
> **Use case:** Officer speaks Kannada (or English), system understands, replies in
> Kannada with optional English transcript, low-latency, barge-in capable.
> **Decision (this doc):** Gemini Live API is the **primary** voice stack; the new
> `gemini-3.5-live-translate-preview` model unlocks Kannada-English bidirectional
> translation; `gemini-3.1-flash-live-preview` is the recommended model for
> dialog-shaped turns where the LLM also needs to *reason* (file an FIR, query a
> case, etc.) rather than just translate.

Sources are cited inline per section. All code blocks below are copied from official
Google docs and the `google-gemini/gemini-live-api-examples` repo (commit on `main`
as of June 2026).

---

## 1. What is Gemini Live API

Source: <https://ai.google.dev/gemini-api/docs/live-api>

Gemini Live API is a **stateful bidirectional WebSocket** that streams audio, images,
and text into Gemini and streams audio (and optional text transcripts) back out, with
sub-second first-audio latency. It is purpose-built for voice-first agents.

Core properties:

- **Protocol:** WSS to `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`.
- **Inputs:** PCM 16-bit mono at 16 kHz audio, JPEG images at ≤1 FPS, and text.
- **Outputs:** PCM 16-bit mono at 24 kHz audio, plus optional text transcripts of
  both the user's speech (`input_audio_transcription`) and the model's speech
  (`output_audio_transcription`).
- **Languages:** 97 BCP-47 languages on the dialog models; 70+ on the translate model.
  Kannada (`kn`) is confirmed supported on both (see §2).
- **Barge-in:** The model halts mid-utterance when the user starts speaking; the
  client receives a `serverContent.interrupted` signal so we can flush the playback
  queue.
- **Tool use:** Function calling and Google Search grounding in the same session.
- **Session resumption:** `sessionResumption` config lets a dropped WebSocket
  resume mid-conversation.

For KSP Saathi this means one socket carries: officer's Kannada speech in, optional
mid-call grounded tool calls (e.g. `lookup_case(fir_id)`), and the assistant's
Kannada spoken response back — no separate STT/TTS pipeline to babysit.

---

## 2. Translate / Transcribe Mode (Gemini 3.5 Live Translate)

Sources:
- <https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-live-3-5-translate/>
- <https://ai.google.dev/gemini-api/docs/live-api/live-translate>

Released **9 June 2026**. Public preview on the Gemini API and AI Studio; private
preview in Google Meet; rolled into Google Translate (Android/iOS) globally.

The translate model is a different animal from the dialog models:

| Aspect | `gemini-3.5-live-translate-preview` | `gemini-3.1-flash-live-preview` |
|---|---|---|
| Job | Speech-to-speech translate, preserves prosody | Conversational agent, reasons, calls tools |
| Languages | 70+ | 97 |
| Output | Translated audio in target language | Native dialog response, can be any language |
| Tool use | No (translation only) | Yes (function calling, Search) |
| Cost (audio in) | $3.50 / 1M tokens ($0.0053/min) | $3.00 / 1M tokens ($0.005/min) |
| Cost (audio out) | $21.00 / 1M tokens ($0.0315/min) | $12.00 / 1M tokens ($0.018/min) |

**Kannada confirmation:** The Live API language table lists Kannada with BCP-47 code
`kn` (full code for our case: `kn-IN`). It is supported on **both** the translate
model (70+ list) and the dialog/native-audio models (97 list).

How translate mode is enabled — the magic field is `translation_config`:

```python
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    translation_config=types.TranslationConfig(
        target_language_code="kn",     # Kannada
        echo_target_language=True       # if user already speaks Kannada, repeat it back
    ),
)
```

`echo_target_language=True` is important for our use case: if the officer already
speaks Kannada, the model still produces Kannada audio (instead of falling silent
because there is "nothing to translate"). Set it to `False` if you only want to
translate when the source differs from the target.

Latency claim from the announcement: "just a few seconds behind the speaker
throughout the session." [UNCERTAIN — Google did not publish a P50/P95 number.]

---

## 3. Available Models

Source: <https://ai.google.dev/gemini-api/docs/models> + pricing page.

| Model ID | Purpose | Modalities | Status |
|---|---|---|---|
| `gemini-3.1-flash-live-preview` | High-quality low-latency dialog | Audio in/out, text, tools | **New Preview** — recommended for our agent |
| `gemini-3.5-live-translate-preview` | Real-time speech-to-speech translation | Audio in/out | **New Preview** — recommended for pure translate |
| `gemini-2.5-flash-native-audio-preview-12-2025` | Earlier native-audio dialog | Audio in/out | Preview |
| `gemini-2.5-flash-preview-native-audio-dialog` | Original native-audio dialog | Audio in/out | Preview (older) |

**Recommendation for KSP Saathi:** start on `gemini-3.1-flash-live-preview`. The
officer needs a *thinking* assistant that can answer "show me yesterday's open
FIRs," not just an interpreter. Use `gemini-3.5-live-translate-preview` as a
fallback in a dedicated "interpret this witness statement" sub-mode where the user
wants raw translation rather than reasoning.

---

## 4. Python SDK Setup

Source: <https://ai.google.dev/gemini-api/docs/live-api>, repo `command-line/python/main.py`.

```bash
pip install google-genai pyaudio
export GEMINI_API_KEY="AIza..."   # or set GOOGLE_API_KEY
```

Minimal shape:

```python
import asyncio
from google import genai
from google.genai import types

client = genai.Client()  # picks up GEMINI_API_KEY

MODEL = "gemini-3.1-flash-live-preview"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "You are a helpful and friendly AI assistant.",
    "input_audio_transcription": {},
    "output_audio_transcription": {},
}

async def main():
    async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
        # send + receive in TaskGroup ...
        pass

asyncio.run(main())
```

Auth: API key in `GEMINI_API_KEY` for prototyping; for production frontends, mint
ephemeral tokens server-side and hand them to the browser — never ship the master
key to the client.

---

## 5. Sending Audio

Source: <https://ai.google.dev/gemini-api/docs/live-api/live-translate>.

Format requirements (hard — wrong sample rate = garbled input):

| Field | Value |
|---|---|
| Encoding | Raw 16-bit PCM, little-endian, mono |
| Input sample rate | **16000 Hz** |
| Chunk size | ~100 ms (e.g. 1600 samples = 3200 bytes) |
| MIME type | `audio/pcm;rate=16000` |

Python (from `command-line/python/main.py`):

```python
await session.send_realtime_input(
    audio=types.Blob(data=chunk_bytes, mime_type="audio/pcm;rate=16000")
)
```

JavaScript: chunks are sent as **base64-encoded** PCM:

```javascript
session.sendRealtimeInput({
  audio: {
    data: chunk.toString('base64'),
    mimeType: "audio/pcm;rate=16000"
  }
});
```

Don't batch beyond ~100 ms — longer chunks defeat VAD and barge-in.

---

## 6. Receiving Audio + Text

Each server message arrives as a `serverContent` object that may contain any
combination of:

- `model_turn.parts[].inline_data.data` — a chunk of PCM (24 kHz on output).
- `output_transcription.text` — incremental ASCII transcript of what the model is
  *speaking* (delivered roughly word-by-word).
- `input_transcription.text` — incremental transcript of what the *user* said
  (useful for showing live captions to the officer).
- `interrupted = true` — user barged in; **flush the audio playback queue
  immediately**, otherwise the user hears stale audio for ~1 second after they
  start talking.

Pattern (from `main.py`):

```python
async for response in session.receive():
    sc = response.server_content
    if not sc:
        continue
    if sc.model_turn:
        for part in sc.model_turn.parts:
            if part.inline_data and isinstance(part.inline_data.data, bytes):
                audio_queue_output.put_nowait(part.inline_data.data)
    if sc.output_transcription:
        print(sc.output_transcription.text, end="", flush=True)
    if sc.input_transcription:
        print(f"\033[3m{sc.input_transcription.text}\033[0m", end="", flush=True)
```

Order of arrival is **not** strictly aligned: input transcripts can lag audio by a
few hundred ms, and output transcript chunks can arrive *after* the audio they
describe. Render them on independent streams in the UI.

---

## 7. Translate Use Case — Our Key Pattern

End-to-end Python for "Officer speaks Kannada → KSP Saathi understands → replies in
Kannada":

```python
import asyncio
from google import genai
from google.genai import types
import pyaudio

client = genai.Client()
MODEL = "gemini-3.1-flash-live-preview"  # dialog model, not the pure-translate one

SYSTEM_INSTRUCTION = """You are Saathi, an AI investigator assistant for the
Karnataka State Police. You converse in Kannada when the officer speaks Kannada
and in English when they speak English. Be concise, factual, and respectful.
Never invent case numbers or evidence; if you don't know, say so in the same
language the officer used. When asked to file an FIR, draft it in formal Kannada
suitable for KSP records."""

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=SYSTEM_INSTRUCTION,
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    # No translation_config needed — the dialog model auto-detects Kannada
    # and replies in Kannada when prompted in Kannada.
)

pya = pyaudio.PyAudio()
mic_q = asyncio.Queue(maxsize=5)
spk_q = asyncio.Queue()

async def mic_in():
    stream = await asyncio.to_thread(
        pya.open, format=pyaudio.paInt16, channels=1, rate=16000,
        input=True, frames_per_buffer=1024,
    )
    while True:
        data = await asyncio.to_thread(stream.read, 1024, exception_on_overflow=False)
        await mic_q.put({"data": data, "mime_type": "audio/pcm;rate=16000"})

async def send_loop(session):
    while True:
        msg = await mic_q.get()
        await session.send_realtime_input(audio=msg)

async def recv_loop(session):
    while True:
        async for resp in session.receive():
            sc = resp.server_content
            if not sc: continue
            if sc.interrupted:
                # flush playback so user hears their own barge-in clean
                while not spk_q.empty(): spk_q.get_nowait()
                continue
            if sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and isinstance(p.inline_data.data, bytes):
                        spk_q.put_nowait(p.inline_data.data)
            if sc.input_transcription:
                print(f"[OFFICER] {sc.input_transcription.text}", flush=True)
            if sc.output_transcription:
                print(f"[SAATHI ] {sc.output_transcription.text}", flush=True)

async def play_loop():
    out = await asyncio.to_thread(
        pya.open, format=pyaudio.paInt16, channels=1, rate=24000, output=True,
    )
    while True:
        chunk = await spk_q.get()
        await asyncio.to_thread(out.write, chunk)

async def main():
    async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
        print("KSP Saathi ready. Speak Kannada or English.")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(mic_in())
            tg.create_task(send_loop(session))
            tg.create_task(recv_loop(session))
            tg.create_task(play_loop())

asyncio.run(main())
```

**Variant for "pure interpreter" sub-mode** (e.g. witness gives statement in
Kannada, officer reads the English transcript). Swap to the translate model and
add `translation_config`:

```python
MODEL = "gemini-3.5-live-translate-preview"
CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    translation_config=types.TranslationConfig(
        target_language_code="en",   # Kannada in → English out
        echo_target_language=False,
    ),
)
```

Multi-turn is automatic — the WebSocket stays open and the model carries
conversational state until the session closes or hits the 15-minute audio-only
session cap (see §9).

---

## 8. JavaScript / Web SDK (for our Next.js frontend)

Source: `command-line/node/main.mts` from the examples repo.

```bash
npm install @google/genai
```

Browser caveat: **don't ship your API key in client-side JS.** The examples repo
explicitly warns:

> WARNING: Do not use API keys in client-side (browser based) applications.
> Consider using Ephemeral Tokens instead.

For Datathon, the cleanest path is: Next.js API route mints an ephemeral token on
demand, browser uses it to open a Live session directly. Skeleton (TypeScript,
adapted from the Node example):

```typescript
import { GoogleGenAI, Modality, type LiveServerMessage } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: ephemeralToken });
const model = 'gemini-3.1-flash-live-preview';

const config = {
  responseModalities: [Modality.AUDIO],
  systemInstruction: "You are Saathi, a Karnataka police investigator AI...",
  inputAudioTranscription: {},
  outputAudioTranscription: {},
};

const responseQueue: LiveServerMessage[] = [];

const session = await ai.live.connect({
  model,
  config,
  callbacks: {
    onopen: () => console.log('connected'),
    onmessage: (m) => responseQueue.push(m),
    onerror: (e) => console.error(e.message),
    onclose: (e) => console.log('closed', e.reason),
  },
});

// Browser: capture mic via Web Audio API
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const ctx = new AudioContext({ sampleRate: 16000 });
const source = ctx.createMediaStreamSource(stream);
const processor = ctx.createScriptProcessor(2048, 1, 1);

processor.onaudioprocess = (e) => {
  const float32 = e.inputBuffer.getChannelData(0);
  const pcm16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    pcm16[i] = Math.max(-1, Math.min(1, float32[i])) * 0x7FFF;
  }
  const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
  session.sendRealtimeInput({
    audio: { data: b64, mimeType: 'audio/pcm;rate=16000' },
  });
};
source.connect(processor);
processor.connect(ctx.destination);

// Receive and play 24kHz PCM
// Decode base64 → Int16Array → schedule into an AudioBufferSourceNode
```

`ScriptProcessorNode` is deprecated; for production rewrite the capture leg as an
`AudioWorklet` so it runs off the main thread. [UNCERTAIN — the official examples
repo uses the Node `mic` package, not browser AudioWorklets; verify Web Audio
sample-rate downsampling works on Safari/iOS before demoing on a Karnataka
officer's phone.]

---

## 9. Pricing + Limits

Source: <https://ai.google.dev/pricing>.

Audio billing: **25 tokens per second of audio**, both directions.

| Model | Audio in | Audio out | Free tier |
|---|---|---|---|
| `gemini-3.1-flash-live-preview` | $3.00 / 1M (~$0.005/min) | $12.00 / 1M (~$0.018/min) | Yes (rate-limited) |
| `gemini-3.5-live-translate-preview` | $3.50 / 1M (~$0.0053/min) | $21.00 / 1M (~$0.0315/min) | Yes (rate-limited) |
| `gemini-2.5-flash-native-audio-preview-12-2025` | $3.00 / 1M | $12.00 / 1M | Yes |

**Hackathon back-of-envelope:** a 5-minute officer ↔ Saathi exchange on
`gemini-3.1-flash-live-preview` with roughly equal in/out audio:
`5 × $0.005 + 5 × $0.018 = $0.115` per conversation. 1000 demo conversations ≈
**$115**. Translate model is ~2x for the output leg.

Session caps (Live API capabilities page):

- **Audio-only session: 15 minutes** before forced close — use `sessionResumption`
  to bridge.
- Audio + video session: 2 minutes.
- Context window: 32k tokens on `gemini-3.1-flash-live-preview`, 128k on native
  audio models.

---

## 10. India Region

Vertex AI docs page for Live API didn't surface a region list in our fetch.
[UNCERTAIN — could not confirm `asia-south1` (Mumbai) availability for Live API
through the docs alone.]

What we **do** know:

- The `generativelanguage.googleapis.com` endpoint (Gemini Developer API, what
  `google-genai` SDK uses by default) is a global endpoint — latency is
  geo-routed, not pinned to a region. Officers in Bengaluru will be served from
  the nearest Google PoP regardless.
- For Vertex AI (`aiplatform.googleapis.com`) you *do* pick a region; Mumbai
  (`asia-south1`) is a standard Vertex region for *batch* Gemini calls. Whether
  Vertex *Live* is in `asia-south1` yet — verify before final demo by attempting
  a connection from a Bengaluru-located client.

**Recommendation for the datathon:** use the Gemini Developer API endpoint (no
region picker, fastest path to a working demo). Migrate to Vertex `asia-south1`
only if KSP procurement requires data-residency in India.

---

## 11. Latency Benchmarks

Official Google claims:

- "Sub-second native audio streaming" for `gemini-2.5-flash-live-preview`.
- "Low-latency Live API model for real-time dialogue" — no number given for
  `gemini-3.1-flash-live-preview`.
- Translate model: "just a few seconds behind the speaker throughout the
  session."

[UNCERTAIN — Google has not published P50/P95 first-token-audio latency. Plan to
measure end-to-end on our actual mic → speak path in the first dev session.]

---

## 12. Sample Code (full files we can copy)

### 12a. Python — full mic-in / speaker-out loop

Source: `google-gemini/gemini-live-api-examples/command-line/python/main.py`,
adapted to our Saathi system instruction.

```python
import asyncio
from google import genai
import pyaudio

client = genai.Client()

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

MODEL = "gemini-3.1-flash-live-preview"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": (
        "You are Saathi, an AI investigator assistant for Karnataka State "
        "Police. Reply in Kannada when addressed in Kannada, English when "
        "addressed in English. Be concise, factual, never invent case data."
    ),
    "output_audio_transcription": {},
    "input_audio_transcription": {},
}

audio_queue_output = asyncio.Queue()
audio_queue_mic = asyncio.Queue(maxsize=5)
audio_stream = None

async def listen_audio():
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
        input=True, input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    kwargs = {"exception_on_overflow": False} if __debug__ else {}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm"})

async def send_realtime(session):
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)

async def receive_audio(session):
    while True:
        turn = session.receive()
        async for response in turn:
            sc = response.server_content
            if not sc: continue
            if sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data and isinstance(part.inline_data.data, bytes):
                        audio_queue_output.put_nowait(part.inline_data.data)
            if sc.output_transcription:
                print(sc.output_transcription.text, end="", flush=True)
            if sc.input_transcription:
                print(f"\033[3m{sc.input_transcription.text}\033[0m", end="", flush=True)
        while not audio_queue_output.empty():
            audio_queue_output.get_nowait()

async def play_audio():
    stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE, output=True,
    )
    while True:
        bytestream = await audio_queue_output.get()
        await asyncio.to_thread(stream.write, bytestream)

async def run():
    try:
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            print("Connected. Speak now.")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_realtime(session))
                tg.create_task(listen_audio())
                tg.create_task(receive_audio(session))
                tg.create_task(play_audio())
    finally:
        if audio_stream: audio_stream.close()
        pya.terminate()

if __name__ == "__main__":
    try: asyncio.run(run())
    except KeyboardInterrupt: pass
```

### 12b. TypeScript / Node — full mic-in / speaker-out loop

Source: `google-gemini/gemini-live-api-examples/command-line/node/main.mts`.

```typescript
import { GoogleGenAI, Modality, type LiveServerMessage } from '@google/genai';
import mic from 'mic';
import Speaker from 'speaker';

const ai = new GoogleGenAI({});
const model = 'gemini-3.1-flash-live-preview';
const config = {
  responseModalities: [Modality.AUDIO],
  systemInstruction: "You are Saathi, KSP investigator AI. Kannada or English.",
  outputAudioTranscription: {},
  inputAudioTranscription: {},
};

async function live() {
  const responseQueue: LiveServerMessage[] = [];
  const audioQueue: Buffer[] = [];
  let speaker: Speaker | null = null;

  function createSpeaker() {
    if (speaker) { process.stdin.unpipe(speaker); speaker.end(); }
    speaker = new Speaker({ channels: 1, bitDepth: 16, sampleRate: 24000 });
    process.stdin.pipe(speaker);
  }

  async function messageLoop() {
    while (true) {
      while (responseQueue.length === 0) await new Promise(r => setImmediate(r));
      const m = responseQueue.shift()!;
      const sc = m.serverContent;
      if (!sc) continue;
      if (sc.interrupted) { audioQueue.length = 0; continue; }
      if (sc.modelTurn?.parts) {
        for (const p of sc.modelTurn.parts) {
          if (p.inlineData?.data) audioQueue.push(Buffer.from(p.inlineData.data, 'base64'));
        }
      }
      if (sc.inputTranscription?.text) process.stdout.write(`\x1b[3m${sc.inputTranscription.text}\x1b[0m`);
      if (sc.outputTranscription?.text) process.stdout.write(sc.outputTranscription.text);
    }
  }

  async function playbackLoop() {
    while (true) {
      if (audioQueue.length === 0) {
        if (speaker) { process.stdin.unpipe(speaker); speaker.end(); speaker = null; }
        await new Promise(r => setImmediate(r));
      } else {
        if (!speaker) createSpeaker();
        const chunk = audioQueue.shift()!;
        await new Promise<void>(r => speaker!.write(chunk, () => r()));
      }
    }
  }

  messageLoop(); playbackLoop();

  const session = await ai.live.connect({
    model, config,
    callbacks: {
      onopen: () => console.log('connected'),
      onmessage: (m) => responseQueue.push(m),
      onerror: (e) => console.error(e.message),
      onclose: (e) => console.log('closed', e.reason),
    },
  });

  const micInstance = mic({ rate: '16000', bitwidth: '16', channels: '1' });
  const micInputStream = micInstance.getAudioStream();
  micInputStream.on('data', (data: Buffer) => {
    session.sendRealtimeInput({
      audio: { data: data.toString('base64'), mimeType: "audio/pcm;rate=16000" }
    });
  });
  micInstance.start();
}

live().catch(console.error);
```

For the Next.js frontend, lift the `session` plumbing into a server route, mint an
ephemeral token, and replace `mic`/`Speaker` with `getUserMedia` + Web Audio (see
§8 sketch).

---

## 13. Gotchas

1. **Audio format mismatch is silent.** If you send 44.1 kHz or stereo or float32,
   you don't get an error — the model just hears garbled noise and either says
   nothing or hallucinates. Always assert the source is 16-bit PCM mono 16 kHz
   before opening the session. Output is 24 kHz; if you pipe it through a 16 kHz
   speaker the user hears chipmunk Saathi.

2. **Barge-in needs queue flushing.** When `serverContent.interrupted = true`
   arrives, drop everything in your audio playback buffer immediately — otherwise
   the user hears 1-2 seconds of stale model speech *after* they've started
   interrupting, which feels broken.

3. **15-minute audio-only session cap.** Long interrogation sessions will be cut
   off. Either chunk into multiple sessions or enable `sessionResumption` in the
   setup config so the WebSocket can reconnect with state intact.

4. **API key vs. ADC vs. ephemeral tokens.**
   - Dev: `GEMINI_API_KEY` env var works for both SDKs.
   - Vertex path: Application Default Credentials (`gcloud auth
     application-default login`).
   - **Browser:** mint ephemeral tokens server-side, never expose the long-lived
     key. Doc: <https://ai.google.dev/gemini-api/docs/ephemeral-tokens>.

5. **Transcript and audio are not strictly aligned.** Input transcripts can lag
   audio by hundreds of ms; output transcript chunks can arrive after the audio
   they describe. Render them independently — don't try to lock them to the
   same UI tick.

6. **`responseLogprobs`, `responseSchema`, `responseMimeType` are unsupported on
   Live.** If you copy a `generationConfig` from a regular Gemini call, strip
   those fields or setup will fail.

7. **Tool-call cancellation exists.** Server can send
   `BidiGenerateContentToolCallCancellation`; your function-call handler must be
   re-entrant and idempotent — if a `lookup_case(fir_id)` is cancelled mid-flight
   because the officer barged in, don't double-charge the downstream DB.

8. **Translate model has no tool use.** Don't pick `gemini-3.5-live-translate-preview`
   if Saathi needs to call functions in the same turn — switch to
   `gemini-3.1-flash-live-preview` for those flows.

9. **Kannada audio quality during preview.** The model is in *preview*; expect
   occasional dropped phonemes on rapid Dakshina Kannada / Mangalorean accents.
   Plan to log audio + transcript pairs in dev so we can sample-check accuracy
   before the demo. [UNCERTAIN — no public WER number for Kannada specifically.]

10. **Region / data residency.** Defaulting to the Gemini Developer API endpoint
    means traffic terminates wherever Google's global frontend routes it — not
    necessarily in India. If KSP requires in-India residency, that is a
    Vertex-on-`asia-south1` migration *and* an open verification ([UNCERTAIN] —
    see §10). Don't promise residency in the pitch deck without confirming.

---

## Quick reference card

| Need | Use |
|---|---|
| Officer voice chat, Kannada+English | `gemini-3.1-flash-live-preview` + system instruction |
| Pure interpreter (witness Kannada → English text) | `gemini-3.5-live-translate-preview` + `translation_config` |
| Live captions on screen | `input_audio_transcription={}` + `output_audio_transcription={}` |
| Tool calls (FIR lookup, case query) | dialog model only, NOT the translate model |
| Browser auth | ephemeral tokens, never the master key |
| Long interrogations | `sessionResumption` config |
| Mic in | 16 kHz PCM16 mono, MIME `audio/pcm;rate=16000`, 100 ms chunks |
| Speaker out | 24 kHz PCM16 mono |
