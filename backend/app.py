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
import json
import tempfile
import os

from db import get_session, init_db
from generate import generate as generate_output
from models import Generation, Recording, Transcript
from prompts import PROMPTS

# ---------------------------
# CONFIGURATION
# ---------------------------

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

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

def _run_transcription(recording_id: int, tmp_path: str):
    """Background worker: uploads to AssemblyAI, polls for completion, and
    persists the result. Runs off the request thread so /transcribe can
    return immediately instead of blocking for the full transcription time."""
    db = get_session()
    recording = db.get(Recording, recording_id)
    recording.status = "transcribing"
    db.commit()

    try:
        config = aai.TranscriptionConfig(speaker_labels=True)
        transcriber = aai.Transcriber(config=config)
        result = transcriber.transcribe(tmp_path)

        if result.status == aai.TranscriptStatus.error:
            raise RuntimeError(result.error)

        utterances = None
        if result.utterances:
            utterances = json.dumps(
                [{"speaker": u.speaker, "text": u.text} for u in result.utterances]
            )

        transcript = Transcript(
            recording_id=recording.id,
            text=result.text,
            utterances=utterances,
            assemblyai_job_id=result.id,
        )
        db.add(transcript)
        recording.status = "transcribed"
        db.commit()
        logger.info(f"Transcription complete for recording_id={recording.id}")
    except Exception as e:
        logger.error(f"Transcription failed for recording_id={recording.id}: {e}")
        recording.status = "failed"
        recording.error_message = str(e)
        db.commit()
    finally:
        db.close()
        os.remove(tmp_path)


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]

    db = get_session()
    recording = Recording(filename=audio_file.filename or "recording", status="uploaded")
    db.add(recording)
    db.commit()
    recording_id = recording.id
    db.close()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    threading.Thread(
        target=_run_transcription, args=(recording_id, tmp_path), daemon=True
    ).start()

    return jsonify({"recording_id": recording_id, "status": "transcribing"}), 202

@app.route("/generate", methods=["POST"])
def generate_route():
    data = request.get_json(silent=True) or {}
    transcript_id = data.get("transcript_id")
    mode = data.get("mode")

    if not transcript_id:
        return jsonify({"error": "No transcript_id provided"}), 400
    if mode not in PROMPTS:
        return jsonify({"error": f"Invalid mode. Must be one of: {list(PROMPTS)}"}), 400

    db = get_session()
    transcript = db.get(Transcript, transcript_id)
    if not transcript:
        db.close()
        return jsonify({"error": f"No transcript found with id {transcript_id}"}), 404

    try:
        output = generate_output(transcript.text, mode)
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500

    generation = Generation(transcript_id=transcript.id, mode=mode, output_text=output)
    db.add(generation)
    db.commit()
    generation_id = generation.id
    db.close()

    return jsonify({"generation_id": generation_id, "output": output})

@app.route("/recordings", methods=["GET"])
def list_recordings():
    db = get_session()
    recordings = db.query(Recording).order_by(Recording.uploaded_at.desc()).all()
    result = [
        {
            "id": r.id,
            "filename": r.filename,
            "title": r.title,
            "status": r.status,
            "error_message": r.error_message,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        }
        for r in recordings
    ]
    db.close()
    return jsonify(result)

@app.route("/recordings/<int:recording_id>", methods=["GET"])
def get_recording(recording_id):
    db = get_session()
    recording = db.get(Recording, recording_id)
    if not recording:
        db.close()
        return jsonify({"error": f"No recording found with id {recording_id}"}), 404

    transcripts = [
        {
            "id": t.id,
            "text": t.text,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "generations": [
                {
                    "id": g.id,
                    "mode": g.mode,
                    "output_text": g.output_text,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in t.generations
            ],
        }
        for t in recording.transcripts
    ]
    result = {
        "id": recording.id,
        "filename": recording.filename,
        "title": recording.title,
        "status": recording.status,
        "error_message": recording.error_message,
        "uploaded_at": recording.uploaded_at.isoformat() if recording.uploaded_at else None,
        "transcripts": transcripts,
    }
    db.close()
    return jsonify(result)

# ---------------------------
# MAIN ENTRY
# ---------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
