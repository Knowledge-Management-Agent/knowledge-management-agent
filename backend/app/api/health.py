from fastapi import APIRouter

from app.config import get_settings
from app.rag.store import get_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "indexed_chunks": get_store().count(),
    }
