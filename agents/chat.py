"""Endpoint conversationnel /chat (Phase 4, tâche 3) — RAG simple sur les
tables SQL : la question sert d'abord à identifier les titres concernés,
dont les données réelles sont assemblées en contexte avant tout appel LLM.
Pas de recherche vectorielle ici (voir `agents/reports.py` pour l'usage de
pgvector, réservé aux rapports/notes longs, tâche 4 de la Phase 4)."""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import company_knowledge, external_analysis, jane_knowledge, mistral_client, web_search
from agents.context import security_snapshot
from agents.george_veille import BIOFUEL_RENEWABLE_GAS_COMPANIES
from ingestion.models import CompanyFundamentals, Decision, PatternDetected, Security

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("proposee", "confirmee")

# Mots-clés d'intention "apprends ceci" — demandé directement par
# l'utilisateur ("to learn on the go"), reconnus seulement en DÉBUT de la
# partie de la question avant le premier ":" (ex. "ajoute à tes skills cette
# information : ..."), jamais n'importe où dans la phrase (voir
# `_extract_taught_knowledge`) : "ajoute"/"retiens" sont aussi des verbes
# ordinaires qui apparaissent au milieu d'une vraie question financière.
# Volontairement une liste de mots-clés larges plutôt qu'une correspondance
# exacte de phrase : tolère "ajoute à tes connaissances", "ajoutes à tes
# skills", "retiens ceci :", etc. sans avoir à les énumérer toutes.
TEACH_INTENT_KEYWORDS = ("ajoute", "ajoutes", "retiens", "retenez", "mémorise", "memorise", "apprends", "note ceci", "note bien")

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


def _extract_taught_knowledge(question: str) -> str | None:
    """Reconnaît une intention "apprends ceci" dans la question elle-même —
    demandé directement par l'utilisateur ("to learn on the go") : envoyer
    depuis le chat une phrase comme "ajoute à tes skills cette information :
    <contenu>" doit faire persister `<contenu>` dans `jane_knowledge`
    (`agents/jane_knowledge.py`, déjà l'infrastructure RAG générale du
    projet — pgvector + dédoublonnage par similarité cosinus), réutilisable
    ensuite pour n'importe quelle question ultérieure, pas seulement une
    liste d'entreprises précise.

    Découpage volontairement simple : mot-clé d'intention avant le premier
    ':', contenu après. Pas d'appel LLM ici — une intention "j'enseigne
    quelque chose" est un signal fort et peu ambigu (contrairement à
    l'extraction de nom d'entreprise dans `agents/external_analysis.py`, qui
    a besoin du LLM car la formulation y est bien plus libre), et
    l'important est justement de stocker le contenu tel quel, sans
    reformulation qui risquerait de perdre ou déformer une information."""
    if ":" not in question:
        return None
    intent, _, content = question.partition(":")
    intent_lower = intent.lower()
    # Ancré en DÉBUT de segment (`re.match`, pas `re.search`) plutôt qu'une
    # simple présence n'importe où : un mot-clé comme "ajoute" ou "retiens"
    # est aussi un verbe ordinaire au milieu d'une vraie question financière
    # ("un investisseur ajoute des actions Alpha SA à son portefeuille : quel
    # est l'impact ?", "je retiens que le secteur est en croissance : qu'en
    # penses-tu ?") — une frontière de mot seule (`\b...\b` n'importe où dans
    # la phrase) ne suffit pas à écarter ce cas, trouvé en `/code-review`.
    # Une véritable intention "enseigne-moi ceci" se formule quasi toujours
    # à l'impératif en tête de phrase ("Ajoute à tes skills...", "Retiens
    # ceci :", "Note bien :"), jamais noyée au milieu d'une autre question.
    if not any(re.match(rf"\s*{re.escape(keyword)}\b", intent_lower) for keyword in TEACH_INTENT_KEYWORDS):
        return None
    content = content.strip()
    return content or None


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
    Match sur une frontière de mot (`\\b`) pour le symbole ET pour le nom,
    pas une simple sous-chaîne : la racine d'un symbole de deux lettres
    (ex. "AC" pour Accor, "EL" pour EssilorLuxottica) apparaît sinon à
    l'intérieur de mots français ordinaires ("ac" dans "achat", "el" dans
    "quelles"), ce qui reconnaissait des titres sans rapport avec la
    question. **Même piège trouvé une seconde fois côté nom, en direct** :
    l'entreprise suivie nommée "SES" (SESG.PA) était reconnue à tort dans
    n'importe quelle question contenant le mot "penses" ("pen-SES"), avec
    pour conséquence concrète de faire croire au code qu'un titre pertinent
    avait été trouvé — court-circuitant entièrement le repli
    `company_news_knowledge`/recherche web pour une société hors référentiel
    (ex. "que penses-tu de Haffner ?" ne cherchait jamais "Haffner" sur le
    web, `titres_reconnus` contenant déjà "SES" sans rapport). `s.name` peut
    contenir plusieurs mots (ex. "Air Liquide") : `\\b...\\b` fonctionne
    correctement de part et d'autre de la phrase complète échappée, pas
    seulement autour d'un seul mot."""
    all_securities = db.execute(select(Security)).scalars().all()
    question_lower = question.lower()
    matches = [
        s
        for s in all_securities
        if re.search(rf"\b{re.escape(s.symbol.lower().split('.')[0])}\b", question_lower)
        or re.search(rf"\b{re.escape(s.name.lower())}\b", question_lower)
    ]
    return matches[:limit]


def _fundamentals_summary(db: Session, symbol: str) -> dict | None:
    """Instantané fondamentaux/entreprise le plus récent (`company_fundamentals`,
    alimentée quotidiennement par `ingestion/fundamentals.py`, voir
    `GET /securities/{symbol}/fundamentals`) — demandé directement par
    l'utilisateur pour enrichir l'analyse de George au-delà du seul signal
    technique (figure/confiance/décision) avec du contexte économique réel :
    secteur, industrie, activité. `None` si l'import quotidien n'a encore
    jamais tourné pour ce titre (nullable par construction, jamais inventé)."""
    stmt = (
        select(CompanyFundamentals)
        .where(CompanyFundamentals.symbol == symbol)
        .order_by(CompanyFundamentals.observed_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return None
    return {
        "secteur": row.sector,
        "industrie": row.industry,
        "activite": row.long_business_summary,
        "capitalisation": row.market_cap,
    }


def _find_biofuel_company(question: str) -> str | None:
    """Reconnaissance par nom dans la question, même principe que
    `find_relevant_securities` mais pour la petite liste hors référentiel de
    `agents/george_veille.py:BIOFUEL_RENEWABLE_GAS_COMPANIES` — pas besoin
    d'une frontière de mot ici, ces noms sont assez longs/distinctifs pour
    ne pas apparaître accidentellement à l'intérieur d'un mot français
    ordinaire (contrairement aux racines de symbole à deux lettres)."""
    question_lower = question.lower()
    for name in BIOFUEL_RENEWABLE_GAS_COMPANIES:
        if name.lower() in question_lower:
            return name
    return None


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
    # Intention "apprends ceci" : premier contrôle, avant tout autre
    # traitement — voir `_extract_taught_knowledge`. Rendu déterministe, sans
    # appel LLM, même principe que `_format_opportunities` : confirmer un
    # enregistrement réel ne demande aucune capacité de langage naturel.
    taught_content = _extract_taught_knowledge(question)
    if taught_content is not None:
        # `add_knowledge` embedde via Mistral avant d'écrire : un échec
        # (indisponibilité/rate-limit, déjà un incident réel documenté dans
        # ce projet) doit dégrader comme partout ailleurs dans ce fichier
        # (voir `learned_knowledge` plus bas), pas remonter en 503 brut —
        # seul chemin de `answer_question` qui appelait Mistral sans ce
        # filet avant ce correctif.
        try:
            entry = jane_knowledge.add_knowledge(db, content=taught_content, source_name="Enseigné via /chat")
        except mistral_client.MistralUnavailableError as err:
            logger.warning("Enregistrement d'une connaissance enseignée en échec pour %r : %s", taught_content, err)
            return "Je n'ai pas pu enregistrer cette information pour le moment, réessaie un peu plus tard."
        if entry is None:
            return "C'est déjà dans mes connaissances, je n'ai rien ajouté de nouveau."
        return "C'est noté, j'ai ajouté cette information à mes connaissances."

    securities = find_relevant_securities(db, question)
    snapshots = [
        {
            **security_snapshot(security, _latest_decision(db, security.symbol), _latest_pattern(db, security.symbol)),
            "fondamentaux": _fundamentals_summary(db, security.symbol),
        }
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

    # Actualités récentes des titres suivis reconnus (`company_news_knowledge`,
    # alimentée en continu par `agents/george_veille.py`) — une simple
    # requête DB filtrée par récence, pas un appel réseau, donc aucun coût
    # supplémentaire sur ce chemin par rapport à avant cet ajout. Enrichit
    # l'analyse quantitative de George (figure/confiance/décision) avec du
    # factuel daté, sans jamais remplacer `titres_reconnus`.
    recent_news = [
        {"entreprise": security.name, "resume": entry.content, "source": entry.source_name, "url": entry.source_url}
        for security in securities
        for entry in company_knowledge.get_recent_company_knowledge(db, symbol=security.symbol)
    ]

    # Aucun titre du référentiel suivi (~120 valeurs CAC 40/Mid 60) reconnu
    # dans la question : d'abord `company_news_knowledge` pour une entreprise
    # du secteur biocarburants/gaz renouvelables déjà couverte par la veille
    # continue de George (`agents/george_veille.py:BIOFUEL_RENEWABLE_GAS_COMPANIES`)
    # — rapide, déjà vérifiée multi-sources, aucun appel réseau. Seulement si
    # rien n'est trouvé là, recherche web en direct (agents.web_search,
    # Tavily) pour répondre sur une société vraiment hors de tout périmètre
    # connu de George (demandé directement par l'utilisateur — "poser des
    # questions sur des sociétés en dehors de la liste actuelle").
    # `chat_system.txt` distingue explicitement les trois sources :
    # `titres_reconnus` porte la vraie analyse quantitative de George (figure
    # détectée, confiance, décision), `actualites_recentes`/`resultats_web`
    # ne sont qu'une information générale sans passer par son moteur de
    # détection — jamais présentées comme équivalentes. Un échec de
    # recherche web (pas de clé, Tavily indisponible) dégrade vers une liste
    # vide, comme pour `agents/jane.py:ask`.
    web_results: list[dict] = []
    if not snapshots:
        biofuel_company = _find_biofuel_company(question)
        if biofuel_company is not None:
            recent_news += [
                {"entreprise": biofuel_company, "resume": entry.content, "source": entry.source_name, "url": entry.source_url}
                for entry in company_knowledge.get_recent_company_knowledge(db, company_name=biofuel_company)
            ]
        if not recent_news:
            # Question enrichie de mots-clés génériques plutôt que la
            # question brute — un nom seul et court (ex. "Haffner" sans
            # "Energy") donnait des résultats Tavily pauvres ou vides en
            # pratique (constaté en direct via l'app), le moteur de
            # recherche ayant trop peu de contexte pour cibler une
            # entreprise précise plutôt qu'un nom de famille générique.
            # "perspectives économiques secteur contrats" ajouté ensuite,
            # demandé directement par l'utilisateur pour que l'analyse
            # dépasse un simple résumé d'actualité brute — vérifié en direct
            # contre Tavily : toujours 5 résultats pertinents avec la requête
            # allongée, pas de dégradation.
            search_query = f"{question} société entreprise perspectives économiques secteur contrats"
            try:
                web_results = web_search.search(search_query)
            except web_search.WebSearchUnavailableError as err:
                logger.warning("Recherche web /chat en échec pour %r : %s", search_query, err)
                web_results = []
            if not web_results:
                logger.info("Recherche web /chat sans résultat pour %r", search_query)

    # Analyse technique en direct sur un historique yfinance téléchargé à
    # la volée (agents.external_analysis) — demandé directement par
    # l'utilisateur : "n'importe quelle entreprise mentionnée dans le chat",
    # pas seulement celles déjà connues (biocarburants/gaz renouvelables)
    # ou suivies. Toujours en complément du texte web ci-dessus, jamais à sa
    # place — deux sources différentes (chiffres réellement détectés par le
    # même moteur que l'univers suivi, vs. actualité en langage naturel).
    # Réutilise `biofuel_company` s'il est déjà connu (évite un appel LLM
    # d'extraction inutile) ; sinon extrait un nom d'entreprise de la
    # question elle-même. Toute étape en échec (aucune entreprise trouvée,
    # aucun ticker résolu, aucun historique/figure) dégrade vers `None`.
    company_technical_analysis: dict | None = None
    if not snapshots:
        company_name_for_analysis = biofuel_company or external_analysis.extract_company_name(question)
        if company_name_for_analysis is not None:
            ticker = external_analysis.resolve_ticker(company_name_for_analysis)
            if ticker is not None:
                match = external_analysis.analyze_ticker(ticker)
                if match is not None:
                    company_technical_analysis = {
                        "entreprise": company_name_for_analysis,
                        "ticker": ticker,
                        "figure": match.pattern_type,
                        "confiance": round(match.confidence, 1),
                        "detectee_le": match.detected_at.isoformat(),
                    }

    # Connaissances enseignées via `_extract_taught_knowledge` (voir plus
    # haut) — recherche sémantique systématique, pas seulement pour les
    # questions hors référentiel : contrairement à `resultats_web`, une note
    # apprise par l'utilisateur (ex. "pour les entreprises françaises,
    # regarde plutôt Pappers.fr") peut être pertinente même en complément
    # d'un titre déjà suivi. Échec Mistral (embedding) dégradé vers une
    # liste vide, même principe que le reste du module — ne doit jamais
    # bloquer `/chat`.
    try:
        learned_knowledge = [entry.content for entry in jane_knowledge.search_jane_knowledge(db, question, limit=3)]
    except mistral_client.MistralUnavailableError as err:
        logger.warning("Recherche de connaissances apprises en échec pour %r : %s", question, err)
        learned_knowledge = []

    # Un contexte vide (aucun titre reconnu, aucune décision ouverte, aucune
    # actualité, aucun résultat web, aucune analyse externe, aucune
    # connaissance apprise) est envoyé tel quel : le prompt système impose
    # de le signaler plutôt que d'inventer une réponse.
    context = {
        "question": question,
        "titres_reconnus": snapshots,
        "opportunites_actuelles": opportunities,
        "actualites_recentes": recent_news,
        "resultats_web": web_results,
        "analyse_technique_externe": company_technical_analysis,
        "connaissances_apprises": learned_knowledge,
    }
    system_prompt = mistral_client.load_system_prompt("chat_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)
