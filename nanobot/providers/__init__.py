"""LLM provider abstraction module (minimal build friendly)."""

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.providers.gemini_web_provider import GeminiWebProvider

__all__ = ["LLMProvider", "LLMResponse", "GeminiWebProvider"]
