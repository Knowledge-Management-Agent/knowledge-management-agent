from functools import lru_cache

from app.config import Settings
from app.llm.base import Embedder


@lru_cache
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device="cpu")


class LocalEmbedder(Embedder):
    """Open-source embedding model run in-process (CPU) via
    sentence-transformers -- no API key, no external service, no rate
    limits. Symmetric model (no query/passage prefixing needed), matching
    the flat Embedder.embed(texts) interface every other provider uses."""

    def __init__(self, settings: Settings):
        self._model = _load_model(settings.local_embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.encode(texts)]
