from dataclasses import dataclass

from app.config import Settings, get_settings
from app.llm.base import Embedder
from app.llm.factory import get_embedder
from app.rag.store import ChromaStore, get_store


@dataclass
class RetrievedChunk:
    text: str
    source: str
    title: str
    section: str
    distance: float


class Retriever:
    def __init__(
        self,
        settings: Settings | None = None,
        store: ChromaStore | None = None,
        embedder: Embedder | None = None,
    ):
        self._settings = settings or get_settings()
        self._store = store or get_store()
        self._embedder = embedder or get_embedder()

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self._settings.retrieval_top_k
        [query_embedding] = self._embedder.embed([query])
        hits = self._store.query(query_embedding, top_k=k)
        return [
            RetrievedChunk(
                text=h["text"],
                source=h["metadata"].get("source", "unknown"),
                title=h["metadata"].get("title", ""),
                section=h["metadata"].get("section", ""),
                distance=h["distance"],
            )
            for h in hits
        ]
