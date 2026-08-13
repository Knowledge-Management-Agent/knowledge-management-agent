from app.config import Settings
from app.llm.base import LLMClient


class GroqLLM(LLMClient):
    """Groq exposes an OpenAI-compatible chat completions API, so this
    reuses the `openai` SDK pointed at Groq's base URL instead of a
    dedicated client. Groq has no embeddings API (chat-completion only)."""

    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1"
        )
        self._model = settings.groq_chat_model

    def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages
        )
        return resp.choices[0].message.content or ""
