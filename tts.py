# components/tts.py
import streamlit as st
import io
from gtts import gTTS

class TTSHandler:
    """Handles Text-to-Speech conversion."""

    def synthesize(self, text: str, language_code: str = "en"):
        """Converts a text string into audio bytes."""
        try:
            # Map language codes to gTTS language names
            lang_dict = {"en": "en", "ur": "ur"}
            tts_lang = lang_dict.get(language_code, "en")
            
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            return audio_fp.read()
        except Exception as e:
            st.error(f"Error generating speech: {e}")
            return None