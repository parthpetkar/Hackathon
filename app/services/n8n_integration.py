import os
import requests
import time
from flask import current_app
from app.call_manager import call_manager

def process_with_n8n(call_sid, transcription):
    """Send query to n8n and wait for response"""
    try:
        # Send to n8n webhook
        requests.post(
            os.getenv("N8N_WEBHOOK_URL"),
            json={"query": transcription, "call_sid": call_sid},
            timeout=10
        )
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < 60:  # 60 seconds timeout
            if call_manager.get_response(call_sid):
                return
            time.sleep(2)  # Check every 2 seconds
        
        # Timeout reached
        language = call_manager.get_language(call_sid)
        from app.config import LanguageConfig
        call_manager.set_response(call_sid, LanguageConfig.PROMPTS[language]["error"])
    
    except Exception as e:
        current_app.logger.error(f"n8n processing error: {str(e)}")
        language = call_manager.get_language(call_sid)
        from app.config import LanguageConfig
        call_manager.set_response(call_sid, LanguageConfig.PROMPTS[language]["error"])