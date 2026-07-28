from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Provider-agnostic chat/generation interface. Every backend adapter
    (OpenAI, Azure OpenAI, Claude, Gemini, mock) implements just this."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        ...


class Embedder(ABC):
    """Provider-agnostic embedding interface, kept separate from LLMClient
    since not every LLM provider offers an embeddings API (e.g. Claude)."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
