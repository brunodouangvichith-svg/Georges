"""Jane — second avis analytique synchrone (Phase 4/6 selon la roadmap,
implémenté ici comme un second appel LLM distinct, `mistral-large-latest`,
appelé avant l'explication finale de George). Jane ne détecte aucun pattern
et ne décide jamais — voir `agents/prompts/jane_second_opinion_system.txt`
pour les garde-fous et le corpus de gestion de portefeuille sur lequel elle
s'appuie (détail complet : `Jane_Synthese_Connaissances.md`).

Le rôle de veille méthodologique continue de Jane (catalogue de nouveaux
patterns candidats) n'est PAS dans ce module : il nécessite l'infrastructure
de tâche de fond à faible priorité (queue/worker séparé) qui n'existe pas
avant la Phase 7 — voir `George_Prompts_Claude_Code.md`, section pilier 7."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from agents import mistral_client
from agents.context import decision_context
from agents.explainer import find_pattern_for_decision
from ingestion.models import Decision, Security


def second_opinion(db: Session, decision: Decision) -> str:
    security = db.get(Security, decision.symbol)
    pattern = find_pattern_for_decision(db, decision)
    context = decision_context(decision, pattern, security)
    system_prompt = mistral_client.load_system_prompt("jane_second_opinion_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_LARGE)
