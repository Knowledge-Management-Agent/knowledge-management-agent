from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.security import ROLE_AUTHOR, ROLE_VIEWER, require_role
from app.rag.qa import answer_question

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None


@router.post("", dependencies=[Depends(require_role(ROLE_VIEWER, ROLE_AUTHOR))])
def query(body: QueryRequest):
    return answer_question(body.question, top_k=body.top_k)
