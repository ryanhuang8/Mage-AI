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

ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_begin(self: Type[StreamingClient], event: BeginEvent):
    print(f"Session started: {event.id}")

def on_turn(self: Type[StreamingClient], event: TurnEvent):
    print(f"{event.transcript} ({event.end_of_turn})")

def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
    print(f"Session terminated: {event.audio_duration_seconds} seconds of audio processed")

def on_error(self: Type[StreamingClient], error: StreamingError):
    print(f"Error occurred: {error}")

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

    print("Listening to microphone... Press Ctrl+C to stop.")

    try:
        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))
    finally:
        client.disconnect(terminate=True)

if __name__ == "__main__":
    main()
