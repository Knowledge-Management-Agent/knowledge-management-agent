from app.config import Settings
from app.llm.base import LLMClient


class ClaudeLLM(LLMClient):
    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def generate(self, prompt: str, system: str = "") -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")
