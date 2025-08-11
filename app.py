from io import BytesIO
import os
import requests
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv
import time
import threading

# Load environment variables early to validate them
load_dotenv()

# Validate required environment variables
REQUIRED_ENVS = [
    "TWILIO_ACCOUNT_SID", 
    "TWILIO_AUTH_TOKEN", 
    "TWILIO_NUMBER", 
    "N8N_WEBHOOK_URL", 
    "GROQ_API_KEY"
]
missing_envs = [env for env in REQUIRED_ENVS if not os.getenv(env)]
if missing_envs:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_envs)}")

app = Flask(__name__)

# Constants
LANGUAGE_MAP = {"1": "English", "2": "Hindi", "3": "Marathi"}
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
TIMEOUT = 10  # seconds for external requests
MAX_WAIT_TIME = 60  # Maximum time to wait for n8n response (seconds)
POLL_INTERVAL = 2   # Time between checks for n8n response (seconds)

# Store responses and call states
n8n_responses = {}
active_calls = {}

@app.route("/voice", methods=["POST"])
def voice():
    """Initial language selection menu"""
    resp = VoiceResponse()
    gather = Gather(
        num_digits=1,
        action="/handle-language",
        method="POST",
        timeout=5
    )
    gather.say(
        "For English, press 1. Hindi ke liye 2 dabaiye. Marathi sathi 3 daba.",
        voice="woman",
        language="en-IN"
    )
    resp.append(gather)
    resp.redirect("/handle-language?Digits=1", method="POST")
    return Response(str(resp), mimetype="text/xml")

@app.route("/handle-language", methods=["POST"])
def handle_language():
    """Handle language selection and record query"""
    choice = request.form.get("Digits", "1")
    language = LANGUAGE_MAP.get(choice, "English")

    resp = VoiceResponse()
    resp.say(
        f"You selected {language}. Please state your query after the beep. Press hash when done.",
        voice="woman",
        language="en-IN"
    )
    resp.record(
        max_length=60,
        finish_on_key="#",
        action="/process-recording",
        play_beep=True,
        timeout=3
    )
    return Response(str(resp), mimetype="text/xml")

def process_and_wait_for_n8n(call_sid, transcription):
    """Background task to wait for n8n response"""
    try:
        # Send to n8n webhook
        requests.post(
            os.getenv("N8N_WEBHOOK_URL"),
            json={"query": transcription, "call_sid": call_sid},
            timeout=TIMEOUT
        )
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < MAX_WAIT_TIME:
            if call_sid in n8n_responses:
                active_calls[call_sid] = n8n_responses.pop(call_sid)
                return
            time.sleep(POLL_INTERVAL)
        
        # Timeout reached
        active_calls[call_sid] = "Sorry, we couldn't process your request in time. Please try again later."
    
    except Exception as e:
        app.logger.error(f"Error in n8n processing: {str(e)}")
        active_calls[call_sid] = "An error occurred during processing. Please try again."

@app.route("/process-recording", methods=["POST"])
def process_recording():
    """Process audio recording and transcribe"""
    call_sid = request.form.get("CallSid")
    recording_url = request.form.get("RecordingUrl")
    
    if not recording_url or not call_sid:
        return error_response("Missing recording information")

    try:
        # Download audio securely from Twilio
        audio_response = requests.get(
            f"{recording_url}.wav",
            stream=True,
            timeout=TIMEOUT,
            auth=(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        )
        audio_response.raise_for_status()

        # Load into memory
        audio_stream = BytesIO()
        for chunk in audio_response.iter_content(chunk_size=8192):
            audio_stream.write(chunk)
        audio_stream.seek(0)

        # Transcribe with Groq API
        transcription_resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
            files={"file": ("recording.wav", audio_stream, "audio/wav")},
            data={"model": "whisper-large-v3"},
            timeout=TIMEOUT
        )
        transcription_resp.raise_for_status()

        transcription = transcription_resp.json().get("text", "").strip()
        app.logger.info(f"Transcription for {call_sid}: {transcription}")

        # Start background thread to handle n8n processing
        active_calls[call_sid] = None  # Mark as processing
        threading.Thread(
            target=process_and_wait_for_n8n,
            args=(call_sid, transcription)
        ).start()

        # Create response with periodic checks
        resp = VoiceResponse()
        resp.say("Thank you. We're processing your request. Please wait.", voice="woman", language="en-IN")
        
        # Check every 3 seconds for response
        gather = Gather(
            action=f"/check-response?call_sid={call_sid}",
            method="POST",
            timeout=3,
            num_digits=1
        )
        resp.append(gather)
        resp.redirect(f"/check-response?call_sid={call_sid}", method="POST")
        
        return Response(str(resp), mimetype="text/xml")

    except requests.exceptions.RequestException as e:
        app.logger.error(f"API request failed: {str(e)}")
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
    
    return error_response("Processing error. Please try again later.")

@app.route("/check-response", methods=["POST"])
def check_response():
    """Check if n8n response is ready"""
    call_sid = request.args.get("call_sid") or request.form.get("CallSid")
    
    if not call_sid:
        return error_response("Missing call information")
    
    # Check if response is ready
    response = active_calls.get(call_sid)
    
    resp = VoiceResponse()
    
    if response is None:
        # Still processing
        resp.say("Still processing your request. Please continue holding.", voice="woman", language="en-IN")
        gather = Gather(
            action=f"/check-response?call_sid={call_sid}",
            method="POST",
            timeout=3,
            num_digits=1
        )
        resp.append(gather)
        resp.redirect(f"/check-response?call_sid={call_sid}", method="POST")
    else:
        # Response ready - play it
        resp.say(response, voice="woman", language="en-IN")
        resp.say("Thank you for your query. Goodbye!")
        # Clean up
        if call_sid in active_calls:
            del active_calls[call_sid]
    
    return Response(str(resp), mimetype="text/xml")

@app.route("/n8n-response", methods=["POST"])
def n8n_response():
    """
    Endpoint to receive data from n8n workflow.
    Expected JSON: {"call_sid": "<original_call_sid>", "output": "<message>"}
    """
    data = request.get_json(force=True)
    call_sid = data.get("call_sid")
    message = data.get("output", "").strip()
    
    if not call_sid:
        return {"error": "Missing call_sid"}, 400
    
    if not message:
        return {"error": "Missing output message"}, 400
    
    # Store response for the active call
    n8n_responses[call_sid] = message
    return {"status": "received", "call_sid": call_sid}, 200

def error_response(message):
    """Create standardized error response"""
    resp = VoiceResponse()
    resp.say(message, voice="woman", language="en-IN")
    return Response(str(resp), mimetype="text/xml")

if __name__ == "__main__":
    app.run(port=5000, debug=True)