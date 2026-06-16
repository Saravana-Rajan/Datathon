# Voice Fixtures

Place sample audio files here for `test_e2e_voice_flow.py`:

| File | Description |
|---|---|
| `en_sample.wav` | "Show chain snatching cases near Indiranagar in the last 30 days." (~3 s, 16 kHz mono PCM) |
| `kn_sample.wav` | "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕಳೆದ ೩೦ ದಿನಗಳಲ್ಲಿ ನಡೆದ ಸರಗಳ್ಳತನಗಳನ್ನು ತೋರಿಸಿ" (~4 s, 16 kHz mono PCM) |
| `en_bargein_question.wav` | "Wait, drop the date filter." spoken mid-response. (~2 s) |

These files are **not** checked into git (see `.gitignore`). Either:

1. Record yourself reading the sentences above (any phone voice-recorder works), or
2. Generate via Google Cloud TTS / Gemini Live API, or
3. Download from a teammate's shared drive.

The voice tests will auto-skip with a clear message if any file is missing,
so the rest of the suite still passes in a clean checkout.

## Format requirements

- **Container:** WAV (PCM) — most permissive across STT engines
- **Sample rate:** 16 kHz (resample your phone recording with `ffmpeg -i in.m4a -ar 16000 -ac 1 out.wav`)
- **Channels:** mono
- **Duration:** 2–5 s per file (keeps integration tests under 30 s)
