from flask import Response
from twilio.twiml.voice_response import VoiceResponse, Say
from .config import VoiceConfig, LanguageConfig

def get_voice_response(language, text):
    """Create a VoiceResponse with proper voice settings"""
    resp = VoiceResponse()
    voice_cfg = VoiceConfig.get_voice_config(language)
    resp.say(text, voice=voice_cfg["voice"], language=voice_cfg["language"])
    return resp

def error_response(call_sid=None):
    """Create standardized error response in appropriate language"""
    from .call_manager import call_manager
    language = "English"
    if call_sid:
        language = call_manager.get_language(call_sid)
    
    error_text = LanguageConfig.PROMPTS[language]["error"]
    return Response(str(get_voice_response(language, error_text)), 200, {'Content-Type': 'text/xml'})