from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.base import Embedder, LLMClient
from app.llm.mock_provider import MockEmbedder, MockLLM


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLM()
    if provider == "openai":
        from app.llm.openai_provider import OpenAILLM

        return OpenAILLM(settings)
    if provider == "azure_openai":
        from app.llm.openai_provider import AzureOpenAILLM

        return AzureOpenAILLM(settings)
    if provider == "claude":
        from app.llm.claude_provider import ClaudeLLM

        return ClaudeLLM(settings)
    if provider == "gemini":
        from app.llm.gemini_provider import GeminiLLM

        return GeminiLLM(settings)
    if provider == "groq":
        from app.llm.groq_provider import GroqLLM

        return GroqLLM(settings)
    raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")


def build_embedder(settings: Settings) -> Embedder:
    provider = settings.embedding_provider.lower()
    if provider == "mock":
        return MockEmbedder()
    if provider == "openai":
        from app.llm.openai_provider import OpenAIEmbedder

        return OpenAIEmbedder(settings)
    if provider == "azure_openai":
        from app.llm.openai_provider import AzureOpenAIEmbedder

        return AzureOpenAIEmbedder(settings)
    if provider == "gemini":
        from app.llm.gemini_provider import GeminiEmbedder

        return GeminiEmbedder(settings)
    if provider == "local":
        from app.llm.local_provider import LocalEmbedder

        return LocalEmbedder(settings)
    raise ValueError(f"Unknown embedding_provider: {settings.embedding_provider}")


@lru_cache
def get_llm_client() -> LLMClient:
    return build_llm_client(get_settings())


@lru_cache
def get_embedder() -> Embedder:
    return build_embedder(get_settings())
