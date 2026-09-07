"""Reformulation du texte d'un partage par email (ad hoc, pas une phase du
roadmap) — demandé directement par l'utilisateur : le texte brut envoyé par
email doit être reformulé par Mistral (mise en forme/ton), jamais complété
avec de nouveaux faits. Même contrat anti-hallucination que le reste de
`agents/` (voir `agents/prompts/email_share_system.txt`, règle 1).

Se rabat sur le texte brut, non reformulé, si Mistral est indisponible —
même principe que `engine/scoring.py:predict_confidence` retombant sur
l'heuristique : un échec de mise en forme ne doit jamais bloquer un partage
qui a par ailleurs déjà tout son contenu réel."""
from __future__ import annotations

from agents import mistral_client
from agents.mistral_client import MistralUnavailableError


def format_email_body(raw_text: str) -> str:
    if not raw_text.strip():
        return raw_text
    system_prompt = mistral_client.load_system_prompt("email_share_system.txt")
    try:
        return mistral_client.complete(
            system_prompt, raw_text, model=mistral_client.MODEL_SMALL, allow_fallback=False
        )
    except MistralUnavailableError:
        return raw_text
