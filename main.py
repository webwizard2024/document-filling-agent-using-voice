# main.py
import streamlit as st
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
     
# Import all components from our custom packages
from components.stt import STTHandler
from components.llm_client import LLMClient
from components.tts import TTSHandler
from components.doc_processor import DocumentProcessor
from components.doc_generator import DocumentGenerator

# --- Helper Functions ---

def is_template(text: str) -> bool:
    """Checks if the text looks like a template."""
    return "[" in text and "]" in text or "{{" in text and "}}" in text

def fill_template_from_dict(template_text: str, data_dict: dict) -> str:
    """Fills a template using a dictionary of extracted data with flexible key matching."""
    filled_text = template_text
    
    # Create a mapping of common field name variations
    # In main.py, update the field_mappings dictionary:

    field_mappings = {
    "Full Name": ["Name", "Full Name", "Employee Name", "Person Name"],
    "Name": ["Name", "Full Name", "Employee Name", "Person Name"],
    "Department": ["Department", "Dept", "Team", "Division"],
    "Company": ["Company", "Organization", "Organization Name", "Employer"],
    "Start Date": ["Start Date", "Joining Date", "Hire Date", "Date Joined"],
    "Job Title": ["Job Title", "Position", "Role", "Designation"],
    "Manager Name": ["Manager Name", "Manager", "Supervisor", "Reporting To"],
    "Employee ID": ["Employee ID", "ID", "Employee Number", "Staff ID"],
    "Annual Salary": ["Annual Salary", "Salary", "Compensation", "Pay"]
    }
    
    # For each key in the extracted data, try to find a matching placeholder
    for key, value in data_dict.items():
        # Try the exact key first
        placeholder = f"[{key}]"
        if placeholder in filled_text:
            filled_text = filled_text.replace(placeholder, str(value))
            continue
        
        # If exact match doesn't work, try field mappings
        matched = False
        for standard_key, variations in field_mappings.items():
            if key in variations:
                for variation in variations:
                    placeholder = f"[{variation}]"
                    if placeholder in filled_text:
                        filled_text = filled_text.replace(placeholder, str(value))
                        matched = True
                        break
                if matched:
                    break
        
        # If still not matched, try partial matching
        if not matched:
            for template_placeholder in [p.strip("[]") for p in template_text.split("[") if "]" in p]:
                if key.lower() in template_placeholder.lower() or template_placeholder.lower() in key.lower():
                    placeholder = f"[{template_placeholder}]"
                    filled_text = filled_text.replace(placeholder, str(value))
                    break
    
    return filled_text

def clear_session():
    """Clears the session state to start a new session."""
    st.session_state.history = []
    st.session_state.document_text = ""
    st.session_state.extracted_info = None
    st.session_state.filled_text = None
    st.session_state.doc_buffer = None
    # Reset API usage tracking
    st.session_state.api_usage = {
        "requests": 0,
        "last_reset_date": datetime.now().date()
    }
    st.success("✅ Session cleared! You can now upload a new document.")

def check_daily_quota():
    """Check if we've exceeded our daily quota."""
    today = datetime.now().date()
    
    # Initialize API usage tracking if not present
    if "api_usage" not in st.session_state:
        st.session_state.api_usage = {
            "requests": 0,
            "last_reset_date": today
        }
    
    # Reset counter if it's a new day
    if st.session_state.api_usage["last_reset_date"] != today:
        st.session_state.api_usage["requests"] = 0
        st.session_state.api_usage["last_reset_date"] = today
    
    # Check if we've exceeded the daily limit (20 requests)
    if st.session_state.api_usage["requests"] >= 20:
        return False
    
    return True

def increment_api_usage():
    """Increment the API usage counter."""
    if "api_usage" not in st.session_state:
        st.session_state.api_usage = {
            "requests": 0,
            "last_reset_date": datetime.now().date()
        }
    
    st.session_state.api_usage["requests"] += 1
    print(f"API usage incremented to: {st.session_state.api_usage['requests']}")

def get_remaining_quota():
    """Get information about remaining quota."""
    today = datetime.now().date()
    
    # Initialize API usage tracking if not present
    if "api_usage" not in st.session_state:
        st.session_state.api_usage = {
            "requests": 0,
            "last_reset_date": today
        }
    
    # Reset counter if it's a new day
    if st.session_state.api_usage["last_reset_date"] != today:
        st.session_state.api_usage["requests"] = 0
        st.session_state.api_usage["last_reset_date"] = today
    
    return {
        "remaining_requests": 20 - st.session_state.api_usage["requests"],
        "total_requests": 20,
        "used_requests": st.session_state.api_usage["requests"]
    }

def reset_quota_for_testing():
    """Function to reset quota for testing purposes."""
    st.session_state.api_usage = {
        "requests": 0,
        "last_reset_date": datetime.now().date()
    }
    st.success("API quota reset for testing!")

# --- Main Application Logic ---

def main():
    # Set page configuration and add custom CSS
    st.set_page_config(
        page_title="🧠 Intelligent Voice & Document Assistant", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state - MOVED INSIDE MAIN FUNCTION
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'document_text' not in st.session_state:
        st.session_state.document_text = ""
    if 'extracted_info' not in st.session_state:
        st.session_state.extracted_info = None
    if 'filled_text' not in st.session_state:
        st.session_state.filled_text = None
    if 'doc_buffer' not in st.session_state:
        st.session_state.doc_buffer = None
    if 'api_quota_exceeded' not in st.session_state:
        st.session_state.api_quota_exceeded = False
    if 'audio_error' not in st.session_state:
        st.session_state.audio_error = None
    
    # Enhanced CSS for better UI with fixed text visibility
    st.markdown("""
    <style>
        /* Main app styling */
        .stApp {
            background: linear-gradient(to right, #f8f9fa, #e9ecef);
        }
        
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background: linear-gradient(135deg, #2E0854, #1e3c72);
            color: white;
            border-radius: 0 15px 15px 0;
            box-shadow: 5px 0 15px rgba(0,0,0,0.1);
        }
        
        /* Fix for all text in sidebar */
        section[data-testid="stSidebar"] * {
            color: white !important;
        }
        
        /* Fix for input fields in sidebar */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] select {
            color: black !important;
            background-color: white !important;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        
        /* Fix for file uploader in sidebar */
        section[data-testid="stSidebar"] div[data-testid="stFileUploader"] {
            background-color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px;
            padding: 10px;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stFileUploader"] label {
            color: black !important;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stFileUploader"] span {
            color: black !important;
        }
        
        /* Fix for audio input in sidebar */
        section[data-testid="stSidebar"] div[data-testid="stAudioInput"] {
            background-color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px;
            padding: 10px;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stAudioInput"] label {
            color: black !important;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stAudioInput"] span {
            color: black !important;
        }
        
        /* Fix for expander in sidebar */
        section[data-testid="stSidebar"] .streamlit-expanderHeader {
            background-color: rgba(255, 255, 255, 0.9) !important;
            color: black !important;
        }
        
        section[data-testid="stSidebar"] .streamlit-expanderContent {
            background-color: rgba(255, 255, 255, 0.9) !important;
            color: black !important;
        }
        
        /* Fix for buttons in sidebar */
        section[data-testid="stSidebar"] button {
            background-color: #4B9BFF !important; 
            color: white !important; 
            border: 1px solid #4B9BFF;
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        section[data-testid="stSidebar"] button:hover {
            background-color: #3a7bc8 !important;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        /* Headers styling */
        .stApp h1, .stApp h2, .stApp h3 {
            color: #1e3c72; 
            font-weight: 600;
        }
        
        /* Card styling */
        .card {
            background-color: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        
        /* Chat message styling */
        .stChatMessage {
            border-radius: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        /* File uploader styling */
        .stFileUploader {
            border: 2px dashed #4B9BFF;
            border-radius: 10px;
            padding: 20px;
            background-color: rgba(75, 155, 255, 0.05);
        }
        
        /* Audio input styling */
        .stAudioInput {
            border-radius: 10px;
            overflow: hidden;
        }
        
        /* Download button styling - always visible */
        .stDownloadButton {
            background: linear-gradient(90deg, #4B9BFF, #3a7bc8) !important;
            color: blue !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 10px 20px !important;
            transition: all 0.3s ease !important;
            display: inline-block !important;
            opacity: 1 !important;
        }
        
        .stDownloadButton:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        /* Success/Warning/Error styling */
        .stAlert {
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #f8f9fa;
            border-radius: 10px;
            font-weight: 600;
        }
        
        /* Code block styling */
        .stCode {
            background-color: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid #4B9BFF;
        }
        
        /* Spinner styling */
        .stSpinner {
            color: #4B9BFF;
        }
        
        /* Custom footer */
        .footer {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #6c757d;
            font-size: 14px;
        }
        
        /* Fix for audio input error display */
        div[data-testid="stAudioInput"] div[role="alert"] {
            display: none;
        }
        
        /* Show error only when actually occurred */
        .audio-error {
            display: block !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize all components
    stt_handler = STTHandler()
    llm_client = LLMClient()
    tts_handler = TTSHandler()
    doc_processor = DocumentProcessor()
    doc_generator = DocumentGenerator()

    # --- Main Header ---
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 2.5rem; color: #1e3c72; margin-bottom: 10px;">
            🧠 Intelligent Voice & Document Assistant
        </h1>
        <p style="font-size: 1.2rem; color: #6c757d;">
            Upload documents, fill templates, and get answers using voice commands
        </p>
    </div>
    """, unsafe_allow_html=True)

    # --- Sidebar for Controls ---
    with st.sidebar:
        st.markdown("""
        <div style="padding: 10px 0;">
            <h2 style="color: white; font-size: 1.5rem; margin-bottom: 20px;">
                ⚙️ Controls
            </h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Session controls
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 New Session", type="secondary", use_container_width=True):
                clear_session()
                st.session_state.api_quota_exceeded = False
                st.rerun()
        
        with col2:
            if st.button("📊 Stats", type="secondary", use_container_width=True):
                quota_info = get_remaining_quota()
                st.sidebar.markdown(f"""
                <div style="background-color: rgba(0,0,0,0.3); border-radius: 10px; padding: 15px; margin-top: 10px;">
                    <h4 style="color: white; margin-bottom: 10px;">API Usage</h4>
                    <p style="color: white; margin-bottom: 5px;">Requests Used: {quota_info['used_requests']} / {quota_info['total_requests']}</p>
                    <p style="color: white;">Remaining: {quota_info['remaining_requests']}</p>
                </div>
                """, unsafe_allow_html=True)

        # Add a debug button to reset quota (only visible in development)
        if os.getenv("ENVIRONMENT") == "development":
            if st.button("🔧 Reset Quota (Debug)", type="secondary", use_container_width=True):
                reset_quota_for_testing()
                st.rerun()

        st.markdown("---")

        # Document upload section
        st.markdown("""
        <div style="padding: 10px 0;">
            <h3 style="color: white; font-size: 1.2rem; margin-bottom: 15px;">
                📄 1. Upload Document
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Choose a PDF or DOCX file", 
            type=["pdf", "docx"], 
            key="doc_uploader",
            help="Upload a document or template to work with"
        )
        
        if uploaded_file:
            with st.spinner("Processing document..."):
                st.session_state.document_text = doc_processor.extract_text(uploaded_file)
            st.success("✅ Document processed successfully!")
            
            if is_template(st.session_state.document_text):
                st.info("👉 This looks like a template. Speak to fill in the fields.")
            else:
                st.info("👉 This looks like a full document. Speak to ask questions about it.")

            with st.expander("View Extracted Text"):
                st.write(st.session_state.document_text)

        # Voice input section
        st.markdown("""
        <div style="padding: 10px 0;">
            <h3 style="color: white; font-size: 1.2rem; margin-bottom: 15px;">
                🎤 2. Voice Input
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Display audio error only if it exists
        if st.session_state.audio_error:
            st.error(f"❌ {st.session_state.audio_error}")
            st.session_state.audio_error = None  # Clear the error after displaying
        
        audio_input = st.audio_input(
            "Click to record your voice", 
            key="audio_input",
            help="Click the microphone button to start recording"
        )

        if audio_input:
            if hasattr(audio_input, 'getvalue'):
                audio_bytes = audio_input.getvalue()
            else:
                audio_bytes = audio_input

            with st.spinner("Transcribing audio..."):
                user_text, detected_lang = stt_handler.transcribe(audio_bytes)
            
            if "error" in user_text.lower():
                st.session_state.audio_error = "Transcription failed. Please try again."
                return

            st.session_state.history.append({"role": "user", "text": user_text, "lang": detected_lang})
            with st.chat_message("user", avatar="👤"):
                st.write(user_text)

            with st.spinner("Processing your request..."):
                if is_template(st.session_state.document_text):
                    # --- ROBUST WORKFLOW WITH ERROR HANDLING ---
                    # Step 1: Extract information from user's speech
                    if not check_daily_quota():
                        st.session_state.api_quota_exceeded = True
                        with st.chat_message("assistant", avatar="🤖"):
                            st.error("❌ You have reached your daily API quota. Please wait until tomorrow or upgrade your plan.")
                            st.info("💡 To continue without waiting, consider upgrading your plan at [Google AI Studio](https://ai.google.dev/pricing).")
                        return
                    
                    # Increment API usage BEFORE making the call
                    increment_api_usage()
                    
                    try:
                        extracted_info = llm_client.extract_info(user_text)
                        
                        with st.chat_message("assistant", avatar="🤖"):
                            # --- CORRECTED LOGIC ---
                            # Check if the returned dictionary has an 'error' key
                            if extracted_info.get("error") == "RESOURCE_EXHAUSTED":
                                st.session_state.api_quota_exceeded = True
                                st.error("❌ " + extracted_info.get("message"))
                                st.info("💡 To continue without waiting, consider upgrading your plan at [Google AI Studio](https://ai.google.dev/pricing).")
                                st.info("⏰ Alternatively, you can wait until your quota resets (typically daily) or try again later.")
                            elif extracted_info:
                                # Store in session state for display in main area
                                st.session_state.extracted_info = extracted_info
                                filled_text = fill_template_from_dict(st.session_state.document_text, extracted_info)
                                st.session_state.filled_text = filled_text
                                
                                # Generate the downloadable document
                                with st.spinner("Generating document..."):
                                    doc_buffer = doc_generator.create_docx(filled_text, title="Filled Document")
                                st.session_state.doc_buffer = doc_buffer
                                
                                st.success("✅ Document processed! Check the main content area for results.")
                            else:
                                # This handles the case where no info could be extracted (empty dict)
                                st.warning("⚠️ I couldn't extract any specific information to fill the template. Please try again, speaking more clearly.")
                    except Exception as e:
                        # Handle any unexpected errors
                        st.session_state.api_usage["requests"] -= 1  # Roll back the increment
                        st.error(f"❌ An unexpected error occurred: {str(e)}")
                        print(f"Unexpected error in template processing: {str(e)}")
                else:
                    # --- ORIGINAL WORKFLOW: ANSWER QUESTIONS ---
                    if not check_daily_quota():
                        st.session_state.api_quota_exceeded = True
                        with st.chat_message("assistant", avatar="🤖"):
                            st.error("❌ You have reached your daily API quota. Please wait until tomorrow or upgrade your plan.")
                            st.info("💡 To continue without waiting, consider upgrading your plan at [Google AI Studio](https://ai.google.dev/pricing).")
                        return
                    
                    # Increment API usage BEFORE making the call
                    increment_api_usage()
                    
                    try:
                        ai_response = llm_client.get_response(prompt=user_text, is_document_blank=st.session_state.document_text)
                        
                        with st.chat_message("assistant", avatar="🤖"):
                            if "RESOURCE_EXHAUSTED" in ai_response or "quota" in ai_response.lower():
                                st.session_state.api_quota_exceeded = True
                                st.error("❌ " + ai_response)
                                st.info("💡 To continue without waiting, consider upgrading your plan at [Google AI Studio](https://ai.google.dev/pricing).")
                                st.info("⏰ Alternatively, you can wait until your quota resets (typically daily) or try again later.")
                            else:
                                st.write(ai_response)

                                with st.spinner("Generating speech..."):
                                    audio_output = tts_handler.synthesize(ai_response, language_code=detected_lang)
                                    if audio_output:
                                        st.audio(audio_output, format="audio/mp3")
                    except Exception as e:
                        # Handle any unexpected errors
                        st.session_state.api_usage["requests"] -= 1  # Roll back the increment
                        st.error(f"❌ An unexpected error occurred: {str(e)}")
                        print(f"Unexpected error in question answering: {str(e)}")

    # Display a warning if API quota is exceeded
    if st.session_state.api_quota_exceeded:
        st.warning("⚠️ You have reached your API quota limit. Some features may not work as expected.")

    # --- Main Content Area ---
    if not st.session_state.document_text:
        # Welcome message when no document is uploaded
        st.markdown("""
        <div class="card" style="text-align: center; padding: 40px;">
            <h2 style="color: #1e3c72; margin-bottom: 20px;">Welcome to the Intelligent Voice & Document Assistant</h2>
            <p style="font-size: 1.1rem; color: #6c757d; margin-bottom: 30px;">
                Get started by uploading a document or template from the sidebar
            </p>
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 30px;">
                <div style="text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 10px;">📄</div>
                    <h4>Upload Documents</h4>
                    <p style="color: #6c757d;">Upload PDF or DOCX files</p>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 10px;">🎤</div>
                    <h4>Voice Commands</h4>
                    <p style="color: #6c757d;">Use voice to fill templates or ask questions</p>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 10px;">💬</div>
                    <h4>Get Answers</h4>
                    <p style="color: #6c757d;">Ask questions about your documents</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Display extracted information and filled document if available
        if st.session_state.extracted_info:
            st.markdown("""
            <div class="card">
                <h2>📋 Extracted Information</h2>
            </div>
            """, unsafe_allow_html=True)
            st.json(st.session_state.extracted_info)
            
            st.markdown("""
            <div class="card">
                <h2>📄 Filled Document</h2>
            </div>
            """, unsafe_allow_html=True)
            st.code(st.session_state.filled_text)
            
            if st.session_state.doc_buffer:
                st.markdown('<div style="margin: 20px 0;">', unsafe_allow_html=True)
                st.download_button(
                    label="📄 Download Document",
                    data=st.session_state.doc_buffer,
                    file_name="filled_document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    help="Download the filled document as a DOCX file"
                )
                st.markdown('</div>', unsafe_allow_html=True)

    # --- Display Conversation History ---
    if st.session_state.history:
        st.markdown("""
        <div class="card">
            <h2>💬 Conversation History</h2>
        </div>
        """, unsafe_allow_html=True)
        
        for message in st.session_state.history:
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
                st.write(message["text"])

    # --- Footer ---
    st.markdown("""
    <div class="footer">
        <p>Intelligent Voice & Document Assistant • Powered by Google Gemini AI</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    load_dotenv()
    main()