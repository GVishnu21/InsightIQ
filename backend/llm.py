"""The only place the app talks to Google Gemini.

Every AI request (SQL generation, explanations, summary advice) goes through
`ask_llm`, so changing the model or the provider means editing this one file.
"""

from google import genai
from google.genai import types

from config import GEMINI_MODEL, require_gemini_key

REQUEST_TIMEOUT_MS = 60_000

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Build the client on first use and reuse it afterwards."""
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=require_gemini_key(),
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    return _client


def ask_llm(prompt: str) -> str:
    """Send one prompt to Gemini and return its text.

    Temperature 0 keeps answers as repeatable as the model allows, which matters
    most when it is writing SQL.
    """
    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    return response.text or ""
