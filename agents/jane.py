"""Jane — second avis analytique synchrone (Phase 4/6 selon la roadmap,
implémenté ici comme un second appel LLM distinct, `mistral-large-latest`,
appelé avant l'explication finale de George). Jane ne détecte aucun pattern
et ne décide jamais — voir `agents/prompts/jane_second_opinion_system.txt`
pour les garde-fous et le corpus de gestion de portefeuille sur lequel elle
s'appuie (détail complet : `Jane_Synthese_Connaissances.md`).

`reformulate_formal` (ad hoc, pas une phase du roadmap) est un rôle distinct
et sans rapport avec le second avis ci-dessus : une passe de reformulation
purement stylistique de l'explication déjà écrite par George, jamais un
avis contradictoire — voir `agents/prompts/jane_reformulation_system.txt`.

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
from agents.mistral_client import MistralUnavailableError
from ingestion.models import Decision, Security


def second_opinion(db: Session, decision: Decision) -> str:
    security = db.get(Security, decision.symbol)
    pattern = find_pattern_for_decision(db, decision)
    context = decision_context(decision, pattern, security)
    system_prompt = mistral_client.load_system_prompt("jane_second_opinion_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_LARGE)


def reformulate_formal(raw_explanation: str) -> str:
    """Reformule l'explication déjà produite par George (`explainer.py:
    explain_decision`) dans un registre plus formel — demandé directement
    par l'utilisateur pour l'écran « George explique ». Pas un second avis
    (voir `second_opinion` ci-dessus) : même contenu factuel, seul le
    registre change (voir `agents/prompts/jane_reformulation_system.txt`).
    Retombe sur le texte brut, non reformulé, si Mistral est indisponible —
    même principe que `agents/email_formatter.py:format_email_body` : un
    échec de mise en forme ne doit jamais bloquer une explication déjà
    complète par ailleurs."""
    if not raw_explanation.strip():
        return raw_explanation
    system_prompt = mistral_client.load_system_prompt("jane_reformulation_system.txt")
    try:
        return mistral_client.complete(system_prompt, raw_explanation, model=mistral_client.MODEL_SMALL)
    except MistralUnavailableError:
        return raw_explanation
