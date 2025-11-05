# gen_study/config.py
import os
from dotenv import load_dotenv, find_dotenv

# --- Load .env file safely ---
load_dotenv(find_dotenv())

# --- Flask Secret Key ---
SECRET_KEY = os.getenv("SECRET_KEY", "default-fallback-secret-key")

# --- Gemini Keys ---
# These ENV variables must exist in your .env file, not hardcoded here
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
INTERVIEW_KEY = os.getenv("INTERVIEW_KEY")

# --- Optional: Print to confirm load success ---
print("✅ GEMINI_API_KEY loaded:", bool(GEMINI_API_KEY))
print("✅ INTERVIEW_KEY loaded:", bool(INTERVIEW_KEY))
