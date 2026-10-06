import logging
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider

logger = logging.getLogger("zizzet.llm.factory")


def get_llm_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "gemini":
        try:
            return GeminiProvider()
        except Exception as exc:
            logger.warning("Could not initialize GeminiProvider (%s). Falling back to MockLLMProvider.", exc)
            return MockLLMProvider()

    elif provider_name == "openai":
        try:
            return OpenAIProvider()
        except Exception as exc:
            logger.warning("Could not initialize OpenAIProvider (%s). Falling back to MockLLMProvider.", exc)
            return MockLLMProvider()

    elif provider_name == "mock":
        return MockLLMProvider()

    else:
        logger.warning("Unknown provider '%s'. Defaulting to MockLLMProvider.", provider_name)
        return MockLLMProvider()
