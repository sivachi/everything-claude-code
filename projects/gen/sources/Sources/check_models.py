import google.generativeai as genai
import os

# Using the key from the script
GOOGLE_API_KEY = "AIzaSyArusnTtHc7CY_Y11j2-XaAWbum600PbO0"

genai.configure(api_key=GOOGLE_API_KEY)

try:
    print("Listing models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
