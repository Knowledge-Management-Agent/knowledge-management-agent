import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.security import ROLE_AUTHOR, require_role
from app.ingestion.loader import IngestionService
from app.rag.generation import DOC_TYPES, generate_document

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    doc_type: str
    input_text: str
    use_retrieval: bool = True


class ApproveRequest(BaseModel):
    doc_type: str
    title: str
    content: str


@router.post("", dependencies=[Depends(require_role(ROLE_AUTHOR))])
def generate(body: GenerateRequest):
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {DOC_TYPES}")
    return generate_document(body.doc_type, body.input_text, use_retrieval=body.use_retrieval)


@router.post("/approve", dependencies=[Depends(require_role(ROLE_AUTHOR))])
def approve_and_reingest(body: ApproveRequest):
    """Closes the 'lessons learned feed back into the KB' loop: a
    human-reviewed generated document is written back through the same
    ingestion pipeline used for uploaded files, so future queries can
    retrieve it."""
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {DOC_TYPES}")

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in body.title).strip()
    filename = f"{body.doc_type}_{safe_title or 'untitled'}.md"

    with tempfile.NamedTemporaryFile(
        suffix=".md", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(f"# {body.title}\n\n{body.content}")
        tmp_path = Path(tmp.name)

    try:
        service = IngestionService()
        result = service.ingest_file(tmp_path, source_label=filename)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result
