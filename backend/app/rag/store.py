from functools import lru_cache

import chromadb

from app.config import Settings, get_settings


class ChromaStore:
    def __init__(self, settings: Settings):
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection.add(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def query(self, embedding: list[float], top_k: int) -> list[dict]:
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            hits.append({"text": doc, "metadata": meta, "distance": dist})
        return hits

    def count(self) -> int:
        return self._collection.count()

    def list_documents(self) -> list[dict]:
        got = self._collection.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in got["metadatas"]:
            source = meta.get("source", "unknown")
            if source not in seen:
                seen[source] = {"source": source, "title": meta.get("title", source), "chunks": 0}
            seen[source]["chunks"] += 1
        return list(seen.values())


@lru_cache
def get_store() -> ChromaStore:
    return ChromaStore(get_settings())
