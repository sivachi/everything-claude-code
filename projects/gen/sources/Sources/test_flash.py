import google.generativeai as genai
import os

GOOGLE_API_KEY = "AIzaSyArusnTtHc7CY_Y11j2-XaAWbum600PbO0"
genai.configure(api_key=GOOGLE_API_KEY)

try:
    print("Testing gemini-flash-latest...")
    model = genai.GenerativeModel("models/gemini-flash-latest")
    response = model.generate_content("Hello")
    print("Success:", response.text)
except Exception as e:
    print(f"Error: {e}")
