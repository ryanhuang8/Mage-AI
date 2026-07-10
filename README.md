# Mage AI 🧙

Record or upload any conversation and turn it into something useful — a transcript, a summary, a twitter thread, or (eventually) a structured medical case note. Think "Pocket YC without the hardware": no wearable required, just point it at an audio file.

## How it works

1. **Transcribe** — upload an audio file (`.m4a`, `.mp3`, `.webm`, etc.) and it's sent to AssemblyAI for speaker-labeled transcription.
2. **Generate** — take any stored transcript and turn it into a different format (currently: a twitter thread, or a structured medical case note) via Claude.

Everything is persisted to a SQLite database (`backend/data/mage.db`) with three tables:
- `recordings` — one row per uploaded audio file (filename, status, upload time)
- `transcripts` — one row per completed transcription, linked to a recording
- `generations` — one row per generated output (mode + text), linked to a transcript

This lets you re-run different generation modes on the same transcript without re-transcribing, and keeps a history of everything you've generated.

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your API keys to `backend/.env`:
```
ASSEMBLYAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

Run the API server:
```bash
python3 app.py
```
(Runs on port 5001 — port 5000 conflicts with macOS AirPlay Receiver.)

## API

- `POST /transcribe` — upload an audio file (`multipart/form-data`, field name `audio`). Returns immediately with `{"recording_id", "status": "transcribing"}`; transcription runs in the background. Poll `GET /recordings/<id>` until `status` is `transcribed`.
- `GET /recordings` — list all recordings.
- `GET /recordings/<id>` — full detail: transcript(s) + every generation run on them.
- `POST /generate` — body `{"transcript_id": ..., "mode": "twitter" | "medical_case"}`. Generates and persists the output.

## CLI scripts (`backend/tests/`)

For quick manual testing without the API:
```bash
# transcribe an audio file (also saves a local .txt copy)
python3 tests/transcribe.py path/to/audio.m4a

# generate an output from a transcript already in the DB
python3 tests/generate_test.py <transcript_id> --mode twitter
```

## Frontend

`frontend/` is a Vite + React app — currently just the default scaffold, not yet wired to the backend.
