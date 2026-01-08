# components/llm_client.py
import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError # Import the error class

# Load environment variables when this module is imported
load_dotenv()

class LLMClient:
    """A client to handle interactions with the Google Gemini AI model."""

    def __init__(self):
        """Sets up the connection to the AI."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file.")
        # FIX: Explicitly pass the API key to the constructor
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.1, google_api_key=api_key)

    def get_response(self, prompt: str, is_document_blank: bool = True) -> str:
        """Sends a prompt to the AI and returns the text response."""
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except ChatGoogleGenerativeAIError as e:
            error_message = str(e)
            if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                return "Error: You have reached your free API quota for today. Please wait a while or upgrade your plan to continue."
            else:
                return f"An API error occurred: {e}"

    def extract_info(self, user_input: str) -> dict:
        """
        Extracts key-value pairs from user input and returns them as a dictionary.
        """
        try:
            prompt = f"""
            You are a data extraction expert specializing in employee information. From the user's input below, extract key-value pairs for the following fields:
            
            - Full Name: The person's complete name
            - Employee ID: Any identification number mentioned
            - Department: The specific department or team the person works in (e.g., "Machine Learning", "Data Science", "Engineering")
            - Company: The organization or company name (e.g., "Radiant Technologies", "Google", "Microsoft")
            - Start Date: When the person started working
            - Job Title: The person's role or position
            - Manager Name: The name of their manager or supervisor
            - Annual Salary: The yearly salary amount
            
            IMPORTANT DISTINCTIONS:
            - Department refers to the functional area or team (e.g., "Machine Learning", "Marketing")
            - Company refers to the organization they work for (e.g., "Radiant Technologies")
            - If someone says "I am a [role] at [company]", the [company] is the Company, not the Department
            - If someone says "I work in the [department]", the [department] is the Department
            
            Return the result as a single JSON object. If a piece of information is not present, do not include it in the JSON. Do not add any text before or after the JSON.

            User Input:
            ---
            {user_input}
            ---
            """
            response = self.llm.invoke(prompt)
            # Clean the response and parse it as JSON
            cleaned_response = response.content.strip().strip("```json").strip("```")
            return json.loads(cleaned_response)
        except ChatGoogleGenerativeAIError as e:
            error_message = str(e)
            if "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                # Return a special dictionary to indicate a quota error
                return {"error": "RESOURCE_EXHAUSTED", "message": "You have reached your free API quota for today. Please wait a while or upgrade your plan to continue."}
            else:
                return {"error": "API_ERROR", "message": f"An API error occurred: {e}"}
        except json.JSONDecodeError:
            # If parsing fails, return an empty dictionary
            return {}