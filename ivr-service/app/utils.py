from flask import Response, request
from twilio.twiml.voice_response import VoiceResponse, Say
from .config import VoiceConfig, LanguageConfig
from .services.tts import elevenlabs_tts
import os

def _build_media_url(file_path: str, ephemeral: bool = False) -> str:
    """Return absolute URL (https) for a saved audio file under the app's audio folder."""
    try:
        # Compute relative path under the base audio dir
        rel = os.path.relpath(file_path, start=elevenlabs_tts.audio_dir)
        # Normalize to URL path
        rel = rel.replace("\\", "/")
        base = request.url_root.rstrip("/")
        return f"{base}/media/{rel}"
    except Exception:
        return None

def get_tts_url(language: str, text: str, *, cache: bool = True, ephemeral: bool = False) -> str | None:
    """Synthesize text-to-speech and return a public media URL to play, or None on failure.
    cache: reuse deterministic file for repeated prompts; ephemeral uses unique filenames (no serve-time deletion).
    """
    file_path = elevenlabs_tts.text_to_speech(text=text, language=language, cache=cache)
    if not file_path:
        return None
    return _build_media_url(file_path, ephemeral=ephemeral)

def get_voice_response(language, text):
    """Create a VoiceResponse with proper voice settings"""
    resp = VoiceResponse()
    voice_cfg = VoiceConfig.get_voice_config(language)
    resp.say(text, voice=voice_cfg["voice"], language=voice_cfg["language"])
    return resp

def get_tts_response(language: str, text: str, *, cache: bool = True, ephemeral: bool = False) -> VoiceResponse:
    """Create a VoiceResponse that plays an ElevenLabs TTS file; fallback to Say if needed."""
    resp = VoiceResponse()
    media_url = get_tts_url(language, text, cache=cache, ephemeral=ephemeral)
    if media_url:
        resp.play(media_url)
        return resp
    # Fallback to Twilio's built-in voice if TTS unavailable
    return get_voice_response(language, text)

def error_response(call_sid=None):
    """Create standardized error response in appropriate language"""
    from .call_manager import call_manager
    language = "English"
    if call_sid:
        language = call_manager.get_language(call_sid)
    
    error_text = LanguageConfig.PROMPTS[language]["error"]
    # Prefer TTS for error message, fallback to built-in voice
    resp = get_tts_response(language, error_text)
    return Response(str(resp), 200, {'Content-Type': 'text/xml'})