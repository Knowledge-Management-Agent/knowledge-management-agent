from app.config import Settings
from app.llm.base import Embedder, LLMClient


class GeminiLLM(LLMClient):
    def __init__(self, settings: Settings):
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_chat_model)

    def generate(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = self._model.generate_content(full_prompt)
        return resp.text or ""


class GeminiEmbedder(Embedder):
    def __init__(self, settings: Settings):
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._genai = genai
        self._model = settings.gemini_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            self._genai.embed_content(model=self._model, content=t)["embedding"]
            for t in texts
        ]
