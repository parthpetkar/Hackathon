from flask import request, Response, current_app
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
import threading

from . import app, call_manager
from .config import LanguageConfig
from .utils import get_voice_response, get_tts_response, get_tts_url, error_response
from .services.transcription import transcribe_audio
from .services.n8n_integration import process_with_n8n

@app.route("/voice", methods=["POST"])
def voice():
    """Initial language selection menu"""
    resp = VoiceResponse()
    gather = Gather(
        num_digits=1,
        action="/handle-language",
        method="POST",
        timeout=10
    )
    
    # Keep initial prompt short and in English for DTMF; Twilio Say supports SSML poorly across mixed languages.
    multilingual_prompt = (
        "For English, press 1. हिंदी के लिए 2 दबाएं. मराठी साठी 3 दबा."
    )
    media_url = get_tts_url("English", multilingual_prompt, cache=True, ephemeral=False)
    if media_url:
        gather.play(media_url)
    else:
        # Fallback to Say
        say = Say(multilingual_prompt)
        gather.append(say)
    resp.append(gather)
    return Response(str(resp), mimetype="text/xml")

@app.route("/handle-language", methods=["POST"])
def handle_language():
    """Handle language selection and record query"""
    choice = request.form.get("Digits", "1")
    language = LanguageConfig.LANGUAGE_MAP.get(choice, "English")
    call_sid = request.form.get("CallSid")
    
    # Initialize call in manager
    call_manager.init_call(call_sid, language)
    # Try to store location if Twilio sent it
    lat = request.form.get("CallerLatitude") or request.form.get("Latitude")
    lon = request.form.get("CallerLongitude") or request.form.get("Longitude")
    if lat and lon:
        call_manager.set_location(call_sid, lat, lon)
    # Save region hint if provided by Twilio
    from_city = request.form.get("FromCity")
    from_state = request.form.get("FromState")
    from_country = request.form.get("FromCountry")
    region_hint = ", ".join([x for x in [from_city, from_state, from_country] if x]) or None
    if region_hint:
        call_manager.set_region(call_sid, region_hint)
    
    # Get language-specific prompt
    prompt = LanguageConfig.PROMPTS[language]["selected"]
    resp = get_tts_response(language, prompt, cache=True, ephemeral=False)
    resp.record(
        max_length=60,
        finish_on_key="#",
        action="/process-recording",
        play_beep=True,
        timeout=5
    )
    return Response(str(resp), mimetype="text/xml")

@app.route("/process-recording", methods=["POST"])
def process_recording():
    """Process audio recording and transcribe"""
    call_sid = request.form.get("CallSid")
    recording_url = request.form.get("RecordingUrl")
    
    if not recording_url or not call_sid:
        return error_response(call_sid)
    
    # Transcribe audio
    transcription = transcribe_audio(recording_url, call_sid)
    if not transcription:
        return error_response(call_sid)
    
    current_app.logger.info(f"Transcription for {call_sid}: {transcription}")
    
    # Ensure we have location if provided in this callback
    lat = request.form.get("CallerLatitude") or request.form.get("Latitude")
    lon = request.form.get("CallerLongitude") or request.form.get("Longitude")
    if lat and lon:
        call_manager.set_location(call_sid, lat, lon)
    # Update region hint if present in this callback
    from_city = request.form.get("FromCity")
    from_state = request.form.get("FromState")
    from_country = request.form.get("FromCountry")
    region_hint = ", ".join([x for x in [from_city, from_state, from_country] if x]) or None
    if region_hint:
        call_manager.set_region(call_sid, region_hint)

    # Start background processing via backend
    threading.Thread(
        target=process_with_n8n,
        args=(call_sid, transcription)
    ).start()
    
    # Create response with periodic checks
    language = call_manager.get_language(call_sid)
    processing_text = LanguageConfig.PROMPTS[language]["processing"]
    resp = get_tts_response(language, processing_text, cache=True, ephemeral=False)
    
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

@app.route("/check-response", methods=["POST"])
def check_response():
    """Check if n8n response is ready"""
    call_sid = request.args.get("call_sid") or request.form.get("CallSid")
    
    if not call_sid or not call_manager.get_language(call_sid):
        return error_response(call_sid)
    
    language = call_manager.get_language(call_sid)
    response = call_manager.get_response(call_sid)
    
    resp = VoiceResponse()
    
    if not response:
        # Still processing
        still_processing = LanguageConfig.PROMPTS[language]["still_processing"]
        resp = get_tts_response(language, still_processing)
        gather = Gather(
            action=f"/check-response?call_sid={call_sid}",
            method="POST",
            timeout=3,
            num_digits=1
        )
        resp.append(gather)
        resp.redirect(f"/check-response?call_sid={call_sid}", method="POST")
    else:
        # Response ready - first try to use pre-generated URLs if available
        audio_url = call_manager.get_audio_url(call_sid)
        if audio_url:
            resp.play(audio_url)
        else:
            resp = get_tts_response(language, response, cache=False, ephemeral=True)
        goodbye_text = LanguageConfig.PROMPTS[language]["goodbye"]
        goodbye_url = call_manager.get_goodbye_url(call_sid)
        if not goodbye_url:
            # Use cached, pre-generated file for standard goodbye prompt
            goodbye_url = get_tts_url(language, goodbye_text, cache=True, ephemeral=False)
        if goodbye_url:
            resp.play(goodbye_url)
        else:
            # Fallback to Say for goodbye
            from app.config import VoiceConfig
            voice_cfg = VoiceConfig.get_voice_config(language)
            resp.say(goodbye_text, voice=voice_cfg["voice"], language=voice_cfg["language"])
        call_manager.cleanup_call(call_sid)
    
    return Response(str(resp), mimetype="text/xml")

@app.route("/n8n-response", methods=["POST"])
def n8n_webhook():
    """
    Endpoint to receive data from n8n workflow.
    Expected JSON: {"call_sid": "<original_call_sid>", "output": "<message>"}
    """
    data = request.get_json(force=True)
    call_sid = data.get("call_sid")
    message = data.get("output", "").strip()
    
    if not call_sid or not message:
        return {"error": "Missing parameters"}, 400
    
    # Pre-generate TTS files to avoid generation delays during TwiML response
    language = call_manager.get_language(call_sid)
    audio_url = get_tts_url(language, message, cache=False, ephemeral=True)
    goodbye_text = LanguageConfig.PROMPTS[language]["goodbye"]
    # Use cached, pre-generated file for standard goodbye prompt
    goodbye_url = get_tts_url(language, goodbye_text, cache=True, ephemeral=False)
    call_manager.set_response(call_sid, message, audio_url=audio_url, goodbye_url=goodbye_url)
    return {"status": "received", "call_sid": call_sid}, 200