"""Module d'explication de George (Phase 4, tâche 1) — le LLM ne reçoit
jamais pour instruction de détecter un pattern ou de calculer un score : il
met en mots les résultats déjà produits par le moteur quantitatif (Phase
1-2), séparation imposée dans `agents/prompts/explainer_system.txt`."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from agents.context import decision_context
from ingestion.models import Decision, PatternDetected, Security


def find_pattern_for_decision(db: Session, decision: Decision) -> PatternDetected | None:
    """Figure la plus récente pour le titre de la décision, détectée au plus
    tard à sa création — heuristique de rattachement en l'absence de colonne
    explicite `decisions.pattern_id` dans le schéma actuel (une décision
    n'est pas garantie d'être créée immédiatement après la détection qui l'a
    motivée, mais c'est le meilleur candidat disponible)."""
    stmt = (
        select(PatternDetected)
        .where(PatternDetected.symbol == decision.symbol, PatternDetected.detected_at <= decision.created_at)
        .order_by(PatternDetected.detected_at.desc(), PatternDetected.confidence.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def explain_decision(db: Session, decision: Decision, jane_note: str | None = None) -> str:
    """`jane_note` : note de second avis de `agents.jane.second_opinion`,
    déjà générée par un appel LLM distinct — voir la contrainte du prompt
    Phase 4 (« Jane relit le dossier complet ... appelée juste avant la
    génération de l'explication finale par George »)."""
    security = db.get(Security, decision.symbol)
    pattern = find_pattern_for_decision(db, decision)
    context = decision_context(decision, pattern, security, jane_note)
    system_prompt = mistral_client.load_system_prompt("explainer_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)
