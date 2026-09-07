"""Endpoint conversationnel /chat (Phase 4, tâche 3) — RAG simple sur les
tables SQL : la question sert d'abord à identifier les titres concernés,
dont les données réelles sont assemblées en contexte avant tout appel LLM.
Pas de recherche vectorielle ici (voir `agents/reports.py` pour l'usage de
pgvector, réservé aux rapports/notes longs, tâche 4 de la Phase 4)."""
from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client, web_search
from agents.context import security_snapshot
from ingestion.models import Decision, PatternDetected, Security

OPEN_STATUSES = ("proposee", "confirmee")

# Mots-clés de la question -> type de décision (`decisions.decision_type`) —
# filtrer ici plutôt que de laisser le LLM filtrer/compter lui-même une
# liste de décisions ouvertes : un modèle "small" énumère de façon peu
# fiable une liste de plusieurs dizaines d'entrées JSON (constaté : il ne
# citait qu'un seul titre sur quatorze correspondant à "Achat", et inventait
# le statut de celui-ci). Même principe que le reste de l'architecture LLM
# du projet : le modèle met en mots un résultat déjà calculé, il ne calcule
# jamais lui-même.
DECISION_TYPE_KEYWORDS = {
    "achat": "Achat",
    "acheter": "Achat",
    "renforcer": "Renforcer",
    "surveiller": "Surveiller",
    "alléger": "Alléger",
    "alleger": "Alléger",
    "vendre": "Alléger",
}


def _requested_decision_type(question: str) -> str | None:
    question_lower = question.lower()
    for keyword, decision_type in DECISION_TYPE_KEYWORDS.items():
        if re.search(rf"\b{keyword}\b", question_lower):
            return decision_type
    return None


def find_relevant_securities(db: Session, question: str, limit: int = 5) -> list[Security]:
    """Reconnaissance de titres par correspondance sur le symbole ou le nom
    — le référentiel `securities` (une quarantaine de titres) est assez
    petit pour ne pas justifier d'analyse lexicale plus fine à ce stade.
    Match sur une frontière de mot (`\\b`), pas une simple sous-chaîne : la
    racine d'un symbole de deux lettres (ex. "AC" pour Accor, "EL" pour
    EssilorLuxottica) apparaît sinon à l'intérieur de mots français ordinaires
    ("ac" dans "achat", "el" dans "quelles"), ce qui reconnaissait des titres
    sans rapport avec la question."""
    all_securities = db.execute(select(Security)).scalars().all()
    question_lower = question.lower()
    matches = [
        s
        for s in all_securities
        if re.search(rf"\b{re.escape(s.symbol.lower().split('.')[0])}\b", question_lower)
        or s.name.lower() in question_lower
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


def _open_decisions_summary(db: Session, decision_type: str | None = None, limit: int = 30) -> list[dict]:
    """Décisions actuellement ouvertes (proposées ou confirmées) — fournie en
    plus des titres reconnus dans la question, pour qu'une question générale
    ("quelles sont les opportunités d'achat ?", sans nom de titre précis) ait
    des données réelles à citer plutôt qu'un contexte vide. `decision_type`
    (déjà déduit de la question par `_requested_decision_type`) filtre ici,
    en Python, plutôt que de transmettre la liste complète au LLM."""
    stmt = select(Decision).where(Decision.status.in_(OPEN_STATUSES))
    if decision_type is not None:
        stmt = stmt.where(Decision.decision_type == decision_type)
    stmt = stmt.order_by(Decision.confidence.desc()).limit(limit)
    decisions = db.execute(stmt).scalars().all()
    return [
        {
            "symbole": d.symbol,
            "type": d.decision_type,
            "statut": d.status,
            "confiance": float(d.confidence),
            "prix_entree": float(d.entry_price),
            "take_profit": float(d.take_profit) if d.take_profit is not None else None,
            "stop_loss": float(d.stop_loss) if d.stop_loss is not None else None,
        }
        for d in decisions
    ]


def _format_opportunities(decisions: list[dict], decision_type: str) -> str:
    """Rendu déterministe, sans appel LLM, d'une liste d'opportunités —
    voir `answer_question` pour pourquoi ce cas contourne le modèle."""
    if not decisions:
        return f"Aucune décision de type « {decision_type} » n'est actuellement ouverte (proposée ou confirmée)."
    lines = []
    for d in decisions:
        line = f"- {d['symbole']} ({d['statut']}) : confiance {d['confiance']:.1f} %, entrée {d['prix_entree']:.2f} €"
        if d["take_profit"] is not None:
            line += f", take-profit {d['take_profit']:.2f} €"
        if d["stop_loss"] is not None:
            line += f", stop-loss {d['stop_loss']:.2f} €"
        lines.append(line)
    return f"Opportunités « {decision_type} » actuelles ({len(decisions)}) :\n" + "\n".join(lines)


def answer_question(db: Session, question: str) -> str:
    securities = find_relevant_securities(db, question)
    snapshots = [
        security_snapshot(security, _latest_decision(db, security.symbol), _latest_pattern(db, security.symbol))
        for security in securities
    ]
    requested_type = _requested_decision_type(question)
    opportunities = _open_decisions_summary(db, requested_type)

    # Question générale sur les opportunités d'un type donné (aucun titre
    # nommé) : rendu déterministe en Python plutôt qu'un appel LLM.
    # Constaté empiriquement contre la vraie base : mistral-small-latest
    # énumère de façon peu fiable une liste de plusieurs dizaines d'entrées
    # JSON structurées (il n'en citait qu'une seule sur quatorze, et
    # inventait même son statut) — malgré des instructions explicites dans
    # le prompt système à énumérer chaque entrée. Ce cas ne demande aucune
    # capacité de langage naturel, seulement de restituer fidèlement des
    # données déjà entièrement formées ; le contourner élimine le risque
    # d'omission/invention plutôt que de espérer un meilleur prompt.
    # Limite connue, acceptée telle quelle (trouvée en revue de code en
    # ajoutant le repli web ci-dessous) : ce raccourci gagne toujours sur le
    # repli web quand la question contient un mot-clé de décision, même pour
    # une société hors référentiel — "dois-je vendre Apple ?" retombe ici
    # ("vendre" -> "Alléger") et répond avec les opportunités "Alléger" de
    # George plutôt que de chercher "Apple" sur le web. Corriger proprement
    # demanderait de distinguer "question générale sur les opportunités"
    # d'"une société précise, non reconnue, avec un verbe de décision" sans
    # NLP fiable à cette échelle — accepté plutôt que d'ajouter une
    # heuristique fragile, même logique que le reste de ce module (voir la
    # note sur `mistral-small-latest` énumérant mal une longue liste).
    if not snapshots and requested_type is not None:
        return _format_opportunities(opportunities, requested_type)

    # Aucun titre du référentiel suivi (~120 valeurs CAC 40/Mid 60) reconnu
    # dans la question : recherche web réelle (agents.web_search, Tavily),
    # pour répondre sur une société hors de cet univers (demandé directement
    # par l'utilisateur — "poser des questions sur des sociétés en dehors de
    # la liste actuelle") plutôt que de se limiter à dire qu'aucun titre
    # n'est reconnu. `chat_system.txt` distingue explicitement les deux
    # sources : `titres_reconnus` porte la vraie analyse quantitative de
    # George (figure détectée, confiance, décision), `resultats_web` n'est
    # qu'une information générale sans passer par son moteur de détection —
    # jamais présentée comme équivalente. Un échec de recherche web (pas de
    # clé, Tavily indisponible) dégrade vers une liste vide, comme pour
    # `agents/jane.py:ask`.
    web_results: list[dict] = []
    if not snapshots:
        try:
            web_results = web_search.search(question)
        except web_search.WebSearchUnavailableError:
            web_results = []

    # Un contexte vide (aucun titre reconnu, aucune décision ouverte, aucun
    # résultat web) est envoyé tel quel : le prompt système impose de le
    # signaler plutôt que d'inventer une réponse.
    context = {
        "question": question,
        "titres_reconnus": snapshots,
        "opportunites_actuelles": opportunities,
        "resultats_web": web_results,
    }
    system_prompt = mistral_client.load_system_prompt("chat_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)
