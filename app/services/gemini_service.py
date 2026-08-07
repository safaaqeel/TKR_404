"""
Single Gemini client construction point. Every agent and service imports
from here - never instantiate genai.GenerativeModel() anywhere else,
or you lose the ability to swap models/add retries/rate-limit centrally.
"""
import logging
from app.config import get_settings

logger = logging.getLogger("smart_automation_ai.gemini")

_client = None


def build_gemini_client():
    global _client
    if _client is not None:
        return _client

    import google.generativeai as genai
    settings = get_settings()
    genai.configure(api_key=settings.GEMINI_API_KEY)
    _client = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
    logger.info(f"Gemini client initialized: {settings.GEMINI_MODEL_NAME}")
    return _client


async def generate(prompt: str, system_instruction: str = None, temperature: float = 0.4) -> str:
    """Central generation call used by all agents. Add retry/backoff here once,
    every caller benefits."""
    client = build_gemini_client()
    response = client.generate_content(
        prompt,
        generation_config={"temperature": temperature},
    )
    return response.text


async def generate_stream(prompt: str, system_instruction: str = None):
    """Streaming variant - powers the 'feel like ChatGPT' requirement.
    Route handlers should wrap this in a StreamingResponse."""
    client = build_gemini_client()
    response = client.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text
