import requests
import logging
from app.call_manager import call_manager


def process_with_n8n(call_sid, transcription):
    """Send query to backend /response and set the result for the call."""
    try:
        lat, lon = call_manager.get_location(call_sid)
        region = call_manager.get_region(call_sid)

        payload = {"query": transcription, "call_sid": call_sid}
        if lat is not None and lon is not None:
            payload["lat"] = lat
            payload["lon"] = lon
        if region:
            payload["region"] = region

        resp = requests.post("http://localhost:5000/response", json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Backend error {resp.status_code}: {resp.text}")
        data = resp.json()
        output = (data.get("output") or "").strip()
        if not output:
            raise RuntimeError("Empty output from backend")

        # Pre-generate TTS files similar to former webhook flow
        from app.config import LanguageConfig
        from app.utils import get_tts_url

        language = call_manager.get_language(call_sid)
        audio_url = get_tts_url(language, output, cache=False, ephemeral=True)
        goodbye_text = LanguageConfig.PROMPTS[language]["goodbye"]
        goodbye_url = get_tts_url(language, goodbye_text, cache=True, ephemeral=False)

        call_manager.set_response(call_sid, output, audio_url=audio_url, goodbye_url=goodbye_url)
    except Exception as e:
        logging.getLogger(__name__).error(f"backend processing error: {str(e)}")
        from app.config import LanguageConfig
        language = call_manager.get_language(call_sid)
        call_manager.set_response(call_sid, LanguageConfig.PROMPTS[language]["error"])