class CallManager:
    def __init__(self):
        self.active_calls = {}
        self.app = None
        
    def init_app(self, app):
        self.app = app
        
    def init_call(self, call_sid, language):
        """Initialize a new call with language selection"""
        self.active_calls[call_sid] = {
            'language': language,
            'status': 'processing',
            'response': None,
            'audio_url': None,
            'goodbye_url': None
        }
    
    def set_response(self, call_sid, response, audio_url=None, goodbye_url=None):
        """Store response from n8n workflow"""
        if call_sid in self.active_calls:
            self.active_calls[call_sid]['response'] = response
            self.active_calls[call_sid]['audio_url'] = audio_url
            if goodbye_url is not None:
                self.active_calls[call_sid]['goodbye_url'] = goodbye_url
            self.active_calls[call_sid]['status'] = 'completed'
    
    def get_response(self, call_sid):
        """Get response for a call if available"""
        call = self.active_calls.get(call_sid)
        if call:
            return call.get('response')
        return None
    
    def get_audio_url(self, call_sid):
        """Get audio URL for a call if available"""
        call = self.active_calls.get(call_sid)
        if call:
            return call.get('audio_url')
        return None

    def get_goodbye_url(self, call_sid):
        """Get goodbye audio URL for a call if available"""
        call = self.active_calls.get(call_sid)
        if call:
            return call.get('goodbye_url')
        return None
    
    def get_language(self, call_sid):
        """Get language for the call"""
        call = self.active_calls.get(call_sid)
        if call:
            return call.get('language')
        return "English"
    
    def cleanup_call(self, call_sid):
        """Remove call from active tracking"""
        if call_sid in self.active_calls:
            del self.active_calls[call_sid]

# Singleton instance
call_manager = CallManager()