import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API client
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found. Please ensure it is set in your .env file.")
        exit()
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"An error occurred during API configuration: {e}")
    exit()

print("Checking for available models that support 'generateContent'...\n")

try:
    # List all available models
    for m in genai.list_models():
        # Check if the model supports the 'generateContent' method
        if 'generateContent' in m.supported_generation_methods:
            print(f"Model found: {m.name}")
except Exception as e:
    print(f"An error occurred while listing models: {e}")