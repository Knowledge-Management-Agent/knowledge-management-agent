import uuid
from pathlib import Path

from app.config import Settings, get_settings
from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import parse_file
from app.llm.base import Embedder
from app.llm.factory import get_embedder
from app.rag.store import ChromaStore, get_store


class IngestionService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: ChromaStore | None = None,
        embedder: Embedder | None = None,
    ):
        self._settings = settings or get_settings()
        self._store = store or get_store()
        self._embedder = embedder or get_embedder()

    def ingest_file(self, path: str | Path, source_label: str | None = None) -> dict:
        path = Path(path)
        text, title = parse_file(path)
        source = source_label or path.name

        chunks = chunk_text(
            text,
            chunk_size=self._settings.chunk_size_tokens,
            overlap=self._settings.chunk_overlap_tokens,
        )
        if not chunks:
            return {"source": source, "title": title, "chunks_ingested": 0}

        texts = [c.text for c in chunks]
        embeddings = self._embedder.embed(texts)
        ids = [f"{source}::{uuid.uuid4().hex[:8]}" for _ in chunks]
        metadatas = [
            {
                "source": source,
                "title": title,
                "section": c.section or "",
                "chunk_index": i,
            }
            for i, c in enumerate(chunks)
        ]

        self._store.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return {"source": source, "title": title, "chunks_ingested": len(chunks)}
