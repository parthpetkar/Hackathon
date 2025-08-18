import os
import requests
from io import BytesIO
from flask import current_app

def transcribe_audio(audio_url, call_sid):
    """Transcribe audio using Groq API"""
    try:
        # Download audio from Twilio
        audio_response = requests.get(
            f"{audio_url}.wav",
            stream=True,
            timeout=10,
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
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
            files={"file": ("recording.wav", audio_stream, "audio/wav")},
            data={"model": "whisper-large-v3"},
            timeout=15
        )
        transcription_resp.raise_for_status()

        return transcription_resp.json().get("text", "").strip()
    except Exception as e:
        current_app.logger.error(f"Transcription error: {str(e)}")
        return None