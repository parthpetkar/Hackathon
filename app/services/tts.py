import os
import re
import hashlib
from datetime import datetime
from flask import current_app, has_app_context
from elevenlabs import ElevenLabs

class ElevenLabsTTS:
    """ElevenLabs Text-to-Speech service"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
        
        # Voice mapping for different languages
        self.VOICE_MAP = {
            "English": "pNInz6obpgDQGcFmaJgB",  # Adam - English
            "Hindi": "zgqefOY5FPQ3bB7OZTVR",    # Bella - Multilingual
            "Marathi": "zgqefOY5FPQ3bB7OZTVR"   # Bella - Multilingual
        }
        
        # Base audio directory
        self.audio_dir = os.path.join(os.getcwd(), 'audio')
        os.makedirs(self.audio_dir, exist_ok=True)
    
    def _initialize_client(self):
        """Initialize ElevenLabs client if API key is available"""
        api_key = os.getenv('ELEVENLABS_API_KEY')
        if api_key:
            try:
                self.client = ElevenLabs(api_key=api_key)
                if has_app_context():
                    current_app.logger.debug(f"ElevenLabs client initialized with API key: {api_key[:6]}...")
            except Exception as e:
                if has_app_context():
                    current_app.logger.error(f"Failed to initialize ElevenLabs client: {str(e)}")
                self.client = None
    
    def get_voice_id(self, language):
        """Get voice ID for the specified language"""
        return self.VOICE_MAP.get(language, self.VOICE_MAP["English"])
    
    def _hashed_filename(self, text: str, language: str) -> str:
        """Create a deterministic filename for caching using SHA1 of language+text."""
        digest = hashlib.sha1(f"{language}:{text}".encode("utf-8")).hexdigest()  # nosec - not for security
        return f"{digest}.mp3"

    def is_cached_filename(self, filename: str) -> bool:
        """Return True if filename matches the cached naming scheme (40-hex digest)."""
        return bool(re.fullmatch(r"[0-9a-f]{40}\.mp3", filename))

    def cleanup_ephemeral_files(self, max_age_seconds: int = 1800) -> int:
        """Delete non-cached (ephemeral) mp3 files older than max_age_seconds.
        Returns count of files deleted.
        """
        deleted = 0
        now = datetime.now().timestamp()
        try:
            for root, _dirs, files in os.walk(self.audio_dir):
                for fname in files:
                    if not fname.lower().endswith('.mp3'):
                        continue
                    # Skip cached hashed files
                    if self.is_cached_filename(fname):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        age = now - os.path.getmtime(fpath)
                        if age > max_age_seconds:
                            os.remove(fpath)
                            deleted += 1
                    except Exception:
                        # Best effort
                        pass
        except Exception:
            pass
        return deleted

    def text_to_speech(self, text, language="English", model="eleven_multilingual_v2", cache: bool = True):
        """
        Convert text to speech using ElevenLabs API.
        If cache is True, reuse a deterministic file based on text+language; else create a unique file.
        Returns the audio file path or None if failed.
        """
        if not self.client:
            self._initialize_client()
            if not self.client:
                if has_app_context():
                    current_app.logger.warning("ElevenLabs client not available")
                return None
                
        try:
            voice_id = self.get_voice_id(language)
            
            if has_app_context():
                current_app.logger.debug(
                    f"Generating speech for language={language}, voice_id={voice_id}, model={model}"
                )
            
            # Create language-specific folder
            lang_folder = os.path.join(self.audio_dir, language)
            os.makedirs(lang_folder, exist_ok=True)
            
            # Determine filename (cached or one-off)
            if cache:
                file_name = self._hashed_filename(text, language)
                file_path = os.path.join(lang_folder, file_name)
                if os.path.exists(file_path):
                    if has_app_context():
                        current_app.logger.debug(f"Using cached TTS file: {file_path}")
                    return file_path
            else:
                safe_snippet = re.sub(r'[^a-zA-Z0-9]+', '-', text[:30]).strip('-')
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                file_name = f"{safe_snippet}_{timestamp}.mp3"
            
            file_path = os.path.join(lang_folder, file_name)

            # Generate audio (stream)
            audio_stream = self.client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model,
                text=text
            )
            
            file_path = os.path.join(lang_folder, file_name)
            
            # Save audio
            with open(file_path, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            
            if has_app_context():
                current_app.logger.info(f"Generated audio file: {file_path}")
            return file_path
            
        except Exception as e:
            if has_app_context():
                current_app.logger.error(f"ElevenLabs TTS error: {str(e)}")
            return None
    
    def get_available_voices(self):
        """Get list of available voices"""
        if not self.client:
            self._initialize_client()
            if not self.client:
                return []
                
        try:
            voices = self.client.voices.get_all()
            return [(voice.voice_id, voice.name, voice.category) for voice in voices.voices]
        except Exception as e:
            if has_app_context():
                current_app.logger.error(f"Error fetching voices: {str(e)}")
            return []

    # --------- Pre-generation helpers ---------
    def pre_generate_prompts(self, prompts_dict: dict) -> None:
        """Pre-generate and cache TTS audio files for a nested prompts dict.
        Expects structure: {language: {key: text, ...}, ...}
        """
        if not isinstance(prompts_dict, dict):
            return
        total = 0
        for language, entries in prompts_dict.items():
            if not isinstance(entries, dict):
                continue
            for _key, text in entries.items():
                if not text:
                    continue
                try:
                    # cache=True ensures deterministic filename and skip API if already present
                    self.text_to_speech(text=text, language=language, cache=True)
                    total += 1
                except Exception:
                    # best-effort; continue with the rest
                    pass
        if has_app_context():
            try:
                current_app.logger.info(f"Pre-generated TTS cache for {total} prompt(s)")
            except Exception:
                pass

    def pre_generate_standard_prompts(self) -> None:
        """Pre-generate prompts from app.config.LanguageConfig.PROMPTS."""
        try:
            # Local import to avoid hard dependency at module import time
            from app.config import LanguageConfig
            self.pre_generate_prompts(LanguageConfig.PROMPTS)
        except Exception:
            # No-op if import fails or structure unexpected
            if has_app_context():
                try:
                    current_app.logger.warning("Skipped pre-generation of standard prompts")
                except Exception:
                    pass

# Singleton instance
elevenlabs_tts = ElevenLabsTTS()
