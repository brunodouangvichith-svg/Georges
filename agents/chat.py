"""Endpoint conversationnel /chat (Phase 4, tâche 3) — RAG simple sur les
tables SQL : la question sert d'abord à identifier les titres concernés,
dont les données réelles sont assemblées en contexte avant tout appel LLM.
Pas de recherche vectorielle ici (voir `agents/reports.py` pour l'usage de
pgvector, réservé aux rapports/notes longs, tâche 4 de la Phase 4)."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from agents.context import security_snapshot
from ingestion.models import Decision, PatternDetected, Security


def find_relevant_securities(db: Session, question: str, limit: int = 5) -> list[Security]:
    """Reconnaissance de titres par correspondance sur le symbole ou le nom
    — le référentiel `securities` (une quarantaine de titres) est assez
    petit pour ne pas justifier d'analyse lexicale plus fine à ce stade."""
    all_securities = db.execute(select(Security)).scalars().all()
    question_lower = question.lower()
    matches = [
        s
        for s in all_securities
        if s.symbol.lower().split(".")[0] in question_lower or s.name.lower() in question_lower
    ]
    return matches[:limit]


def _latest_decision(db: Session, symbol: str) -> Decision | None:
    stmt = select(Decision).where(Decision.symbol == symbol).order_by(Decision.created_at.desc()).limit(1)
    return db.execute(stmt).scalars().first()


def _latest_pattern(db: Session, symbol: str) -> PatternDetected | None:
    stmt = (
        select(PatternDetected)
        .where(PatternDetected.symbol == symbol)
        .order_by(PatternDetected.detected_at.desc(), PatternDetected.confidence.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def answer_question(db: Session, question: str) -> str:
    securities = find_relevant_securities(db, question)
    snapshots = [
        security_snapshot(security, _latest_decision(db, security.symbol), _latest_pattern(db, security.symbol))
        for security in securities
    ]

    # Un contexte vide (aucun titre reconnu) est envoyé tel quel : le prompt
    # système impose de le signaler plutôt que d'inventer une réponse.
    context = {"question": question, "titres_reconnus": snapshots}
    system_prompt = mistral_client.load_system_prompt("chat_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)
