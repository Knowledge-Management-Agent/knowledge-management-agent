"""End-to-end smoke test for the RAG pipeline using the mock LLM/embedder
(no external API calls / keys required)."""
import shutil
import tempfile
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.loader import IngestionService
from app.llm.mock_provider import MockEmbedder, MockLLM
from app.rag.generation import generate_document
from app.rag.qa import answer_question
from app.rag.retriever import Retriever
from app.rag.store import ChromaStore

SAMPLE_DOC = """# Restarting the Widget Service

## Procedure
1. SSH into widget-host-01.
2. Run `systemctl restart widget-service`.
3. Confirm health with `curl localhost:9000/health`.
"""


@pytest.fixture
def pipeline(tmp_path):
    settings = Settings(
        chroma_persist_dir=str(tmp_path / "chroma"),
        chroma_collection="test_collection",
        llm_provider="mock",
        embedding_provider="mock",
    )
    store = ChromaStore(settings)
    embedder = MockEmbedder()
    llm = MockLLM()

    doc_path = tmp_path / "widget-runbook.md"
    doc_path.write_text(SAMPLE_DOC, encoding="utf-8")

    ingestion = IngestionService(settings=settings, store=store, embedder=embedder)
    result = ingestion.ingest_file(doc_path, source_label="widget-runbook.md")

    retriever = Retriever(settings=settings, store=store, embedder=embedder)
    return {"result": result, "retriever": retriever, "llm": llm}


def test_ingestion_creates_chunks(pipeline):
    assert pipeline["result"]["chunks_ingested"] > 0
    assert pipeline["result"]["source"] == "widget-runbook.md"


def test_retrieval_finds_relevant_chunk(pipeline):
    hits = pipeline["retriever"].retrieve("how do I restart the widget service?", top_k=3)
    assert hits
    assert any("widget-service" in h.text for h in hits)


def test_qa_returns_answer_with_citation(pipeline):
    result = answer_question(
        "how do I restart the widget service?",
        retriever=pipeline["retriever"],
        llm=pipeline["llm"],
    )
    assert result["answer"]
    assert any(c["source"] == "widget-runbook.md" for c in result["citations"])
    assert "total" in result["timings_ms"]


def test_generation_produces_content(pipeline):
    result = generate_document(
        "runbook",
        "Widget service needs a documented restart procedure.",
        retriever=pipeline["retriever"],
        llm=pipeline["llm"],
    )
    assert result["content"]
    assert result["doc_type"] == "runbook"
