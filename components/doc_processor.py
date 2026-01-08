# components/doc_processor.py
import streamlit as st
import PyPDF2
import docx

class DocumentProcessor:
    """Handles extracting text from uploaded documents."""

    def extract_text(self, uploaded_file) -> str:
        """Extracts text from a PDF or DOCX file."""
        try:
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                return text
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc = docx.Document(uploaded_file)
                return "\n".join([para.text for para in doc.paragraphs])
            else:
                return "Unsupported file type. Please upload a PDF or DOCX file."
        except Exception as e:
            st.error(f"Error reading document: {e}")
            return ""