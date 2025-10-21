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

load_dotenv()

# TODO: Remove duplicates (lines recorded twice)
'''

Possible solution:
- Remove punctuations
- String compare with .lower() of previous line

'''


ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    text = event.transcript.strip()
    if text:
        print(f"{text} ({event.end_of_turn})")
        if event.end_of_turn:
            append_to_file(text)

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
