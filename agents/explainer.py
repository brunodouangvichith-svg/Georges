"""Module d'explication de George (Phase 4, tâche 1) — le LLM ne reçoit
jamais pour instruction de détecter un pattern ou de calculer un score : il
met en mots les résultats déjà produits par le moteur quantitatif (Phase
1-2), séparation imposée dans `agents/prompts/explainer_system.txt`."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from agents.context import decision_context, exit_scenario_context
from ingestion.models import Decision, PatternDetected, Security


def find_pattern_for_decision(db: Session, decision: Decision) -> PatternDetected | None:
    """`decision.pattern_id` (Phase 6, rempli par `engine.propose_decisions`)
    rattache désormais explicitement une décision à la figure qui l'a
    motivée — utilisé en priorité. Les décisions illustratives plus
    anciennes (`ingestion/seed_demo.py`) n'ont pas de `pattern_id` : on
    retombe alors sur l'heuristique historique (la figure la plus récente
    pour ce titre, détectée au plus tard à la création de la décision)."""
    if decision.pattern_id is not None:
        return db.get(PatternDetected, decision.pattern_id)
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


def explain_exit_scenario(
    db: Session,
    decision: Decision,
    result: str,
    pnl_pct: float,
    scenario: str,
    volume_confirmed: bool | None,
) -> str:
    """Met en mots un scénario de sortie déjà décidé par
    `engine.exit_scenarios.classify_exit` (Phase 6, tâche 4) — jamais
    recalculé ici, voir `agents/prompts/exit_scenario_system.txt`."""
    security = db.get(Security, decision.symbol)
    context = exit_scenario_context(decision, security, result, pnl_pct, scenario, volume_confirmed)
    system_prompt = mistral_client.load_system_prompt("exit_scenario_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)
