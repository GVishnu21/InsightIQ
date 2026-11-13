"""Central place for configuration.

Why this file exists: settings such as API keys must not be hard-coded in
source code (anyone who sees the code would see the key). Instead they live in
a local `.env` file, which is git-ignored, and are read from environment
variables here. Every other module imports its settings from this file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env no matter which folder uvicorn is started from.
load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
# Browser origins allowed to call this API (comma-separated).
FRONTEND_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]


def require_gemini_key() -> str:
    """Return the API key, or raise a clear error if it is missing.

    Called when we actually need Gemini (not at import time), so the rest of
    the app, like CSV profiling, still works without a key.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env "
            "(see backend/.env.example)."
        )
    return GEMINI_API_KEY
