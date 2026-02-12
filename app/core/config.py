import os
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

MAX_TEXT_LENGTH = 50000
