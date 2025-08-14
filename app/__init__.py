from flask import Flask, send_from_directory, request
from .call_manager import call_manager
import os

app = Flask(__name__)

# Initialize call manager
call_manager.init_app(app)

# Import routes after app is created
from . import routes

# Static-like route for serving generated TTS media files
@app.route('/media/<path:filename>')
def media(filename: str):
	from .services.tts import elevenlabs_tts
	directory = elevenlabs_tts.audio_dir
	return send_from_directory(directory, filename)

# Warm up and pre-generate static TTS prompts at startup (best-effort)
try:
	from .services.tts import elevenlabs_tts
	elevenlabs_tts.pre_generate_standard_prompts()
except Exception:
	# Don't block app if TTS isn't available
	pass