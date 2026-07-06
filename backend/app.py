# app.py
import threading
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import assemblyai as aai
from assemblyai.streaming.v3 import (
    StreamingClient,
    StreamingClientOptions,
    StreamingParameters,
    StreamingSessionParameters,
    StreamingEvents,
    BeginEvent,
    TurnEvent,
    TerminationEvent,
    StreamingError
)
import tempfile
import os

from generate import generate as generate_output
from prompts import PROMPTS

# ---------------------------
# CONFIGURATION
# ---------------------------

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variable to manage streaming state
stream_thread = None
is_streaming = False
client = None


# ---------------------------
# STREAMING EVENT HANDLERS
# ---------------------------

def on_begin(self, event: BeginEvent):
    logger.info(f"🎤 Session started: {event.id}")

def on_turn(self, event: TurnEvent):
    logger.info(f"🗣️ {event.transcript} (End of turn: {event.end_of_turn})")

    if event.end_of_turn and not event.turn_is_formatted:
        params = StreamingSessionParameters(format_turns=True)
        self.set_params(params)

def on_terminated(self, event: TerminationEvent):
    logger.info(f"🔚 Session terminated: {event.audio_duration_seconds} seconds processed")

def on_error(self, error: StreamingError):
    logger.error(f"❌ Error occurred: {error}")


# ---------------------------
# STREAMING FUNCTION
# ---------------------------

def start_streaming():
    global client, is_streaming

    client = StreamingClient(
        StreamingClientOptions(
            api_key=ASSEMBLYAI_API_KEY,
            api_host="streaming.assemblyai.com",
        )
    )

    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    client.connect(
        StreamingParameters(
            sample_rate=16000,
            format_turns=True,
            end_of_turn_confidence_threshold=0.7,
            min_end_of_turn_silence_when_confident=160,
            max_turn_silence=2400,
            keyterms_prompt=[],
            language="en",
        )
    )

    is_streaming = True
    logger.info("🎧 Listening from microphone...")

    try:
        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))
    finally:
        client.disconnect(terminate=True)
        is_streaming = False


# ---------------------------
# FLASK ROUTES
# ---------------------------

@app.route("/start", methods=["POST"])
def start():
    global stream_thread, is_streaming

    if is_streaming:
        return jsonify({"status": "already streaming"}), 400

    stream_thread = threading.Thread(target=start_streaming, daemon=True)
    stream_thread.start()

    return jsonify({"status": "started"})


@app.route("/stop", methods=["POST"])
def stop():
    global client, is_streaming

    if not is_streaming:
        return jsonify({"status": "not streaming"}), 400

    client.disconnect(terminate=True)
    is_streaming = False
    return jsonify({"status": "stopped"})


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"streaming": is_streaming})

@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]

    # Save temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Upload & transcribe via AssemblyAI
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(tmp_path)
        text = transcript.text
    except Exception as e:
        text = f"Error: {e}"
    finally:
        os.remove(tmp_path)

    return jsonify({"transcript": text})

@app.route("/generate", methods=["POST"])
def generate_route():
    data = request.get_json(silent=True) or {}
    transcript_text = data.get("transcript")
    mode = data.get("mode")

    if not transcript_text:
        return jsonify({"error": "No transcript provided"}), 400
    if mode not in PROMPTS:
        return jsonify({"error": f"Invalid mode. Must be one of: {list(PROMPTS)}"}), 400

    try:
        output = generate_output(transcript_text, mode)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"output": output})

# ---------------------------
# MAIN ENTRY
# ---------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
