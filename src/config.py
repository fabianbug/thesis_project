from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
EXP = BASE / "experiments" / "results"
SEED = 42


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def require(name: str, value: str | None):
    # Error if key is missing
    if not value or not value.strip():
        raise RuntimeError(f"{name} is missing. Add it to your .env")
    return value
