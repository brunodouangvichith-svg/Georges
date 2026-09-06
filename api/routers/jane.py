"""Endpoint `/jane/ask` — question libre à la base de connaissances de Jane
(`jane_knowledge`), en dehors de tout contexte de décision. Voir
`agents/jane.py:ask` pour le RAG pgvector qui assemble le contexte avant
l'appel LLM. Distinct de `POST /chat` (`agents/chat.py`), qui répond sur les
titres/décisions suivis par George — pas sur le savoir méthodologique de
Jane."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.jane import ask
from api.deps import get_db
from api.schemas import JaneAskRequest, JaneAskResponse

router = APIRouter(prefix="/jane", tags=["jane"])


@router.post("/ask", response_model=JaneAskResponse)
def ask_jane(request: JaneAskRequest, db: Session = Depends(get_db)):
    answer = ask(db, request.question)
    return JaneAskResponse(answer=answer)
