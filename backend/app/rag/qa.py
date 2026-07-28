import time

from app.llm.base import LLMClient
from app.llm.factory import get_llm_client
from app.rag.prompts import QA_SYSTEM, QA_TEMPLATE, format_context
from app.rag.retriever import Retriever


def answer_question(
    question: str,
    retriever: Retriever | None = None,
    llm: LLMClient | None = None,
    top_k: int | None = None,
) -> dict:
    retriever = retriever or Retriever()
    llm = llm or get_llm_client()

    t0 = time.perf_counter()
    chunks = retriever.retrieve(question, top_k=top_k)
    t1 = time.perf_counter()

    prompt = QA_TEMPLATE.format(context=format_context(chunks), question=question)
    answer = llm.generate(prompt, system=QA_SYSTEM)
    t2 = time.perf_counter()

    citations = [
        {"source": c.source, "title": c.title, "section": c.section}
        for c in chunks
    ]
    # de-duplicate citations by source while preserving order
    seen = set()
    deduped = []
    for c in citations:
        if c["source"] not in seen:
            seen.add(c["source"])
            deduped.append(c)

    return {
        "answer": answer,
        "citations": deduped,
        "timings_ms": {
            "retrieval": round((t1 - t0) * 1000, 1),
            "generation": round((t2 - t1) * 1000, 1),
            "total": round((t2 - t0) * 1000, 1),
        },
    }
