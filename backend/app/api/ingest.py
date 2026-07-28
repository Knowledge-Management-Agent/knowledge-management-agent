import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.auth.security import ROLE_AUTHOR, ROLE_VIEWER, require_role
from app.ingestion.loader import IngestionService
from app.ingestion.parsers import UnsupportedFileType
from app.rag.store import get_store

router = APIRouter(prefix="/ingest", tags=["ingest"])

_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".html", ".htm", ".md", ".markdown", ".txt"}


@router.post("", dependencies=[Depends(require_role(ROLE_AUTHOR))])
async def ingest_document(file: UploadFile):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        service = IngestionService()
        result = service.ingest_file(tmp_path, source_label=file.filename)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


@router.get("/documents", dependencies=[Depends(require_role(ROLE_VIEWER, ROLE_AUTHOR))])
def list_documents():
    return {"documents": get_store().list_documents(), "total_chunks": get_store().count()}
