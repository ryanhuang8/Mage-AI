#!/usr/bin/env python3
"""
AssemblyAI Transcription Script
Usage: python transcribe.py <path_to_audio.mp3|m4a> [--output transcript.txt]
"""

import argparse
import os
import sys
import time
from dotenv import load_dotenv
import requests

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
BASE_URL = "https://api.assemblyai.com/v2"

HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def upload_audio(file_path: str) -> str:
    """Upload a local audio file to AssemblyAI and return the upload URL."""
    print(f"[1/3] Uploading '{file_path}' to AssemblyAI...")

    def read_file(path, chunk_size=5_242_880):  # 5 MB chunks
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    response = requests.post(
        f"{BASE_URL}/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=read_file(file_path),
    )
    response.raise_for_status()
    upload_url = response.json()["upload_url"]
    print(f"    Upload complete → {upload_url}")
    return upload_url


def request_transcript(audio_url: str) -> str:
    """Submit a transcription job and return the job ID."""
    print("[2/3] Requesting transcription...")

    payload = {
        "audio_url": audio_url,
        "punctuate": True,
        "format_text": True,
        "speaker_labels": True,
    }

    response = requests.post(f"{BASE_URL}/transcript", json=payload, headers=HEADERS)
    response.raise_for_status()
    job_id = response.json()["id"]
    print(f"    Job submitted → ID: {job_id}")
    return job_id


def poll_transcript(job_id: str) -> dict:
    """Poll until the transcript is ready, then return the full result."""
    print("[3/3] Waiting for transcript", end="", flush=True)

    while True:
        response = requests.get(f"{BASE_URL}/transcript/{job_id}", headers=HEADERS)
        response.raise_for_status()
        result = response.json()
        status = result["status"]

        if status == "completed":
            print(" ✓")
            return result
        elif status == "error":
            print()
            raise RuntimeError(f"Transcription failed: {result.get('error')}")
        else:
            print(".", end="", flush=True)
            time.sleep(3)


def format_transcript(result: dict) -> str:
    """Format the transcript with speaker labels, one turn per line."""
    utterances = result.get("utterances")

    # Fallback: no speaker data, just wrap plain text at word boundaries
    if not utterances:
        words = (result.get("text") or "").split()
        lines, line = [], []
        for word in words:
            line.append(word)
            if len(" ".join(line)) >= 80:
                lines.append(" ".join(line))
                line = []
        if line:
            lines.append(" ".join(line))
        return "\n".join(lines)

    # Format each utterance as "Speaker X: <text>" separated by blank lines
    lines = []
    for utt in utterances:
        speaker = f"Speaker {utt['speaker']}"
        lines.append(f"{speaker}: {utt['text']}")

    return "\n\n".join(lines)


def save_transcript(text: str, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nTranscript saved to '{output_path}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Transcribe an audio file using AssemblyAI")
    parser.add_argument("audio_file", help="Path to the MP3 or M4A file")
    parser.add_argument(
        "--output", "-o", default="transcript.txt", help="Output file (default: transcript.txt)"
    )
    args = parser.parse_args()

    if not args.audio_file.lower().endswith((".mp3", ".m4a")):
        print("ERROR: Only .mp3 and .m4a files are supported.")
        sys.exit(1)

    if ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY":
        print("ERROR: Please set your AssemblyAI API key in the script (ASSEMBLYAI_API_KEY).")
        sys.exit(1)

    try:
        upload_url = upload_audio(args.audio_file)
        job_id = request_transcript(upload_url)
        result = poll_transcript(job_id)
        transcript_text = format_transcript(result)

        print("\n" + "─" * 60)
        print("TRANSCRIPT PREVIEW:")
        print("─" * 60)
        print(transcript_text[:600])
        if len(transcript_text) > 600:
            print("\n... [truncated — see output file for full transcript]")

        save_transcript(transcript_text, args.output)

    except FileNotFoundError:
        print(f"ERROR: File not found → '{args.audio_file}'")
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"HTTP ERROR: {e.response.status_code} – {e.response.text}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
