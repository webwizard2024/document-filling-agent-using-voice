# components/stt.py
import streamlit as st
import speech_recognition as sr
import io # Import the io library for in-memory operations

class STTHandler:
    """Handles Speech-to-Text conversion using an in-memory buffer."""

    def __init__(self):
        """Initializes the recognizer."""
        self.recognizer = sr.Recognizer()

    def transcribe(self, audio_bytes) -> tuple[str, str]:
        """Converts audio bytes to text using an in-memory buffer."""
        try:
            # --- THE FIX: Use an in-memory buffer instead of a temp file ---
            audio_buffer = io.BytesIO(audio_bytes)
            
            # Use the recognizer to read from the in-memory buffer
            with sr.AudioFile(audio_buffer) as source:
                audio_data = self.recognizer.record(source)
                
                # Use Google's free web service for transcription.
                text = self.recognizer.recognize_google(audio_data)
                
                # No need to clean up a temp file anymore!
                
                # Detect language (basic implementation)
                detected_lang = "en"  # Default to English
                if any(word in text.lower() for word in ["urdu", "اردو", "میں", "آپ", "ہے"]):
                    detected_lang = "ur"
                
                return text, detected_lang

        except sr.UnknownValueError:
            return "Sorry, I could not understand that.", "en"
        except sr.RequestError as e:
            st.error(f"Could not connect to the speech service. Check your internet connection. Error: {e}")
            return "Error connecting to speech service.", "en"
        except Exception as e:
            st.error(f"An unexpected error occurred during transcription: {e}")
            return "An error occurred.", "en"