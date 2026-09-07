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

Le rôle de veille méthodologique continue de Jane est maintenant partagé
entre deux modules distincts : `agents/jane_knowledge.py` (base de
connaissances `jane_knowledge`, embeddée pgvector, interrogée ci-dessous par
`second_opinion`) et `agents/jane_veille.py` (le sous-agent qui l'alimente).
Le catalogue de nouveaux **patterns chartistes** candidats
(`ingestion.models.PatternCandidate`), lui, n'est PAS couvert par ces deux
modules — il nécessite le scraping réel des sources de méthodologie
(Playwright, non encore ajouté) que `agents/jane_veille.py` documente
explicitement comme hors de son scope actuel.

`second_opinion` persiste chaque note dans `jane_second_opinions`
(`ingestion.models.JaneSecondOpinion`) — jusqu'ici générée à la volée par
`POST /decisions/{id}/explanation` et jamais conservée nulle part, ce qui
empêchait toute évaluation a posteriori de sa pertinence (aucun moyen de la
recroiser avec `decision_outcomes` une fois la décision clôturée).

`ask` (ad hoc, pas une phase du roadmap) est un troisième rôle, sans rapport
avec les deux ci-dessus : le bouton flottant « Ask Jane » de l'écran Univers
mobile, qui interroge `jane_knowledge` en dehors de tout contexte de
décision — contrairement à `second_opinion`, dont le RAG est scopé au type
de décision/figure en cours (`_knowledge_query`), ici la requête RAG est la
question de l'utilisateur elle-même. Pas de persistance (contrairement à
`second_opinion`) : une question libre n'est pas une décision à recroiser
avec un résultat futur.

`ask` interroge aussi `agents.web_search` (Tavily) en complément —
`jane_knowledge.search_jane_knowledge` n'a pas de seuil de pertinence (une
recherche par distance cosinus `ORDER BY ... LIMIT N` renvoie toujours les N
lignes les plus proches, même hors sujet), donc compter les résultats
n'indique jamais fiablement "rien de pertinent trouvé" — c'est pourquoi
`connaissances_pertinentes` et `resultats_web` sont systématiquement fournis
tous les deux au LLM, à charge du prompt système de juger lui-même de la
pertinence de chaque source plutôt qu'un seuil Python arbitraire. Une
recherche web qui échoue (pas de clé, Tavily indisponible) dégrade vers une
liste vide, jamais une erreur bloquante pour toute la réponse."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from agents import jane_knowledge, mistral_client, web_search
from agents.context import decision_context
from agents.explainer import find_pattern_for_decision
from agents.mistral_client import MistralUnavailableError
from ingestion.models import Decision, JaneSecondOpinion, PatternDetected, Security

KNOWLEDGE_MATCHES_LIMIT = 5


def _knowledge_query(decision: Decision, pattern: PatternDetected | None) -> str:
    """Requête texte pour le RAG `jane_knowledge` — pur, aucune DB. Le type
    de décision et le type de figure suffisent à retrouver le savoir
    pertinent (ex. "Fujimoto" pour un renforcement, "RSI"/"MEDAF" pour une
    figure de retournement), sans avoir besoin d'injecter tout le contexte
    structuré déjà envoyé séparément au LLM."""
    parts = [decision.decision_type]
    if pattern is not None:
        parts.append(pattern.pattern_type)
    return " ".join(parts)


def second_opinion(db: Session, decision: Decision) -> str:
    """Génère la note de second avis de Jane et la persiste dans
    `jane_second_opinions` avant de la renvoyer — `decision.id` doit donc
    correspondre à une décision déjà en base (jamais `None`), ce qui est
    toujours le cas côté API (`db.get(Decision, decision_id)` en amont dans
    `api/routers/decisions.py`)."""
    security = db.get(Security, decision.symbol)
    pattern = find_pattern_for_decision(db, decision)
    context = decision_context(decision, pattern, security)
    context["connaissances_pertinentes"] = [
        {"contenu": entry.content, "source": entry.source_name}
        for entry in jane_knowledge.search_jane_knowledge(db, _knowledge_query(decision, pattern), limit=KNOWLEDGE_MATCHES_LIMIT)
    ]
    system_prompt = mistral_client.load_system_prompt("jane_second_opinion_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    note = mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_LARGE)

    db.add(JaneSecondOpinion(decision_id=decision.id, content=note))
    db.commit()
    return note


ASK_KNOWLEDGE_MATCHES_LIMIT = 5


def ask(db: Session, question: str) -> str:
    """Répond à une question libre à partir de `jane_knowledge` et, en
    complément, d'une recherche web réelle — voir le docstring de ce module
    pour la distinction avec `second_opinion` et pour pourquoi les deux
    sources sont toujours fournies ensemble plutôt qu'un repli conditionnel
    en Python. La question elle-même sert de requête RAG *et* de requête web
    (contrairement à `_knowledge_query`, scopé à une décision).
    `agents/prompts/jane_ask_system.txt` instruit Jane de préférer la base de
    connaissances quand elle est réellement pertinente, de se rabattre sur
    les résultats web sinon (en citant leurs sources), et de dire
    honnêtement qu'elle ne sait pas si aucune des deux ne répond vraiment à
    la question."""
    matches = jane_knowledge.search_jane_knowledge(db, question, limit=ASK_KNOWLEDGE_MATCHES_LIMIT)
    try:
        web_results = web_search.search(question)
    except web_search.WebSearchUnavailableError:
        web_results = []
    context = {
        "question": question,
        "connaissances_pertinentes": [{"contenu": entry.content, "source": entry.source_name} for entry in matches],
        "resultats_web": web_results,
    }
    system_prompt = mistral_client.load_system_prompt("jane_ask_system.txt")
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
        return mistral_client.complete(
            system_prompt, raw_explanation, model=mistral_client.MODEL_SMALL, allow_fallback=False
        )
    except MistralUnavailableError:
        return raw_explanation
