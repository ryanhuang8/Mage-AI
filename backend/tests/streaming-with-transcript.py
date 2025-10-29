import logging
from typing import Type
import assemblyai as aai
from dotenv import load_dotenv
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
import os
import re

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
prev_line = ""

OUTPUT_FILE = "../transcripts/transcript_log.txt"

def append_to_file(text: str):
    """Appends text to the transcript file."""
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def on_begin(self: Type[StreamingClient], event: BeginEvent):
    msg = f"Session started: {event.id}"
    print(msg)
    append_to_file(f"\n--- {msg} ---\n")

def on_turn(self: Type[StreamingClient], event: TurnEvent):
    global prev_line
    text = event.transcript.strip()

    if not text:
        return

    print(f"{text} ({event.end_of_turn})")
    if not event.end_of_turn:
        return

    cleaned = re.sub(r"[^A-Za-z0-9\s]", "", text).lower()

    if cleaned == prev_line:
        # Remove last written line and replace it
        try:
            with open(OUTPUT_FILE, "r+", encoding="utf-8") as f:
                lines = f.readlines()
                # Remove any trailing blank lines before last text
                while lines and lines[-1].strip() == "":
                    lines.pop()
                if lines:
                    lines.pop()  # Remove last transcript line
                f.seek(0)
                f.writelines(lines)
                f.truncate()
            print("🧹 Removed previous duplicate line.")
        except FileNotFoundError:
            pass

        # Append the new line
        append_to_file(text)

    else:
        # Normal case: write if it's new
        append_to_file(text)
        prev_line = cleaned

def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
    msg = f"Session terminated: {event.audio_duration_seconds} seconds of audio processed"
    print(msg)
    append_to_file(f"\n--- {msg} ---\n")

def on_error(self: Type[StreamingClient], error: StreamingError):
    msg = f"Error occurred: {error}"
    print(msg)
    append_to_file(f"[ERROR] {msg}")

def main():
    client = StreamingClient(
        options=StreamingClientOptions(api_key=ASSEMBLYAI_API_KEY)
    )

    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    client.connect(
        StreamingParameters(
            sample_rate=16000,
            format_turns=True,
        )
    )

    print("🎙️ Listening to microphone... Press Ctrl+C to stop.")
    append_to_file("\n=== New Session Started ===\n")

    try:
        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))
    finally:
        client.disconnect(terminate=True)
        append_to_file("\n=== Session Ended ===\n")

if __name__ == "__main__":
    main()
