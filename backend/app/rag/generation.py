from app.llm.base import LLMClient
from app.llm.factory import get_llm_client
from app.rag.prompts import GENERATION_SYSTEM, GENERATION_TEMPLATE, format_context
from app.rag.retriever import Retriever

DOC_TYPES = ("runbook", "sop", "kb_article", "rca_summary")


def generate_document(
    doc_type: str,
    input_text: str,
    use_retrieval: bool = True,
    retriever: Retriever | None = None,
    llm: LLMClient | None = None,
    top_k: int | None = None,
) -> dict:
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Unknown doc_type: {doc_type}. Expected one of {DOC_TYPES}")

    retriever = retriever or Retriever()
    llm = llm or get_llm_client()

    chunks = []
    if use_retrieval:
        chunks = retriever.retrieve(input_text, top_k=top_k)

    prompt = GENERATION_TEMPLATE.format(
        context=format_context(chunks), input_text=input_text
    )
    content = llm.generate(prompt, system=GENERATION_SYSTEM[doc_type])

    citations = [
        {"source": c.source, "title": c.title, "section": c.section} for c in chunks
    ]
    seen = set()
    deduped = []
    for c in citations:
        if c["source"] not in seen:
            seen.add(c["source"])
            deduped.append(c)

    return {"doc_type": doc_type, "content": content, "citations": deduped}
