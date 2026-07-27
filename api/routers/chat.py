"""Endpoint `/chat` — question libre en langage naturel (Phase 4, tâche 3),
voir `agents/chat.py` pour le RAG SQL simple qui assemble le contexte avant
l'appel LLM."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.chat import answer_question
from api.deps import get_db
from api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    answer = answer_question(db, request.question)
    return ChatResponse(answer=answer)
