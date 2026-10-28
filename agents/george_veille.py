"""Veille continue d'actualités entreprises pour George (ad hoc, pas une
phase du roadmap) — demandé directement par l'utilisateur : "Georges doit
mettre à jour ses connaissances en continue... scope : entreprises du Cac 40
et midcac 60 et aussi les entreprises du secteur des biocarburants et des
gaz renouvelables". Même discipline "recherche web réelle (Tavily) + synthèse
multi-sources Mistral, pas de scraping site-spécifique" que
`agents/jane_veille.py:collect_veille_web` — voir sa docstring pour le
raisonnement complet (Tavily remplace le besoin de Playwright/Scrapy jamais
ajouté au projet).

Contrairement à la veille de Jane (sujets méthodologiques généraux, sans
lien avec une entreprise précise), celle-ci est scopée par entreprise :
chaque entrée de `company_news_knowledge` porte un `company_name`/`symbol`,
consommée par `agents.chat.answer_question` en complément de
`titres_reconnus` (titres suivis : actualités récentes en plus de l'analyse
quantitative) et à la place du repli web à la volée pour les entreprises
biocarburants/gaz renouvelables déjà couvertes ici.

Volontairement non enregistré dans `agents/collectors/__init__.py:COLLECTORS`
— même précédent et même raison que `collect_veille_web` : une veille de
fond à faible priorité, jamais via l'endpoint HTTP réactif partagé avec les
autres sous-agents. Tourne via `.github/workflows/daily_george_veille.yml`."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import company_knowledge, mistral_client, web_search
from agents.orchestrator.types import CollectedItem
from ingestion.models import Security

# Entreprises du secteur biocarburants/gaz renouvelables hors du référentiel
# `securities` (CAC 40/Mid Cac 60) — demandé explicitement par l'utilisateur,
# qui a ensuite fourni une liste plus large à trier. Chaque nom ci-dessous a
# été vérifié réel ET coté en bourse avant ajout (pas devinée, pas recopiée
# telle quelle) : Neste (Finlande, diesel renouvelable/SAF), Verbio
# (Allemagne, biodiesel/biométhane), Waga Energy (France, biométhane à partir
# de gaz d'enfouissement — notée ici bien qu'une prise de participation
# majoritaire d'EQT en 2025 vise à la retirer de la cote à terme, la veille
# suivra ce changement le moment venu), Global Bioenergies (France,
# hydrocarbures biosourcés/SAF), Gevo (États-Unis, carburants renouvelables),
# Haffner Energy (France, hydrogène/pyrogazéification, Euronext Growth
# ALHAF.PA), Raízen (Brésil, bioéthanol de canne à sucre, B3 RAIZ4), ADM
# (États-Unis, agro-industrie avec activité biocarburants réelle, NYSE ADM).
#
# Volontairement EXCLUS de cette liste, malgré leur présence dans la liste
# plus large fournie par l'utilisateur (vérifié avant d'écarter, pas par
# principe) : TotalEnergies et Engie sont déjà dans `securities` (CAC 40),
# donc déjà couverts par la rotation sur les titres suivis — les y ajouter
# ici ferait doublon. Tereos, Cristal Union et Avril sont des coopératives
# agro-industrielles, non cotées en bourse (confirmé en direct) — pas
# d'actualité "résultats financiers" publique à suivre au même titre qu'une
# société cotée. Cargill est privée. Vol-V, EverGaz, Nature Energy, Prodeval,
# CVE, Roquette, GRDF, Teréga, NaTran n'ont pas pu être confirmés comme
# sociétés cotées de façon indépendante — écartés par prudence plutôt
# qu'ajoutés sur la base d'une liste non vérifiée. Liste à faire évoluer,
# pas figée — `symbol=None` puisqu'aucune de ces entreprises n'a de ligne
# dans `securities`.
BIOFUEL_RENEWABLE_GAS_COMPANIES = [
    "Neste",
    "Verbio",
    "Waga Energy",
    "Global Bioenergies",
    "Gevo",
    "Haffner Energy",
    "Raízen",
    "ADM",
]

# 10/jour x RESULTS_PER_COMPANY (3) = 30 appels Tavily/jour, ~900/mois --
# reste sous le tier gratuit Tavily (1000/mois), contrairement à 30/jour
# (~2700/mois, testé puis abandonné pour cette raison). L'univers combiné de
# ~130 entreprises est couvert en ~13 jours, un compromis fraîcheur/quota.
COMPANIES_PER_RUN = 10
RESULTS_PER_COMPANY = 3

DUPLICATE_STATUS_NOTE = "quasi-doublon ignoré"
ADDED_STATUS_NOTE = "ajoutée à company_news_knowledge"


def _all_companies(db: Session) -> list[dict]:
    """Univers combiné : les valeurs suivies (`securities`, triées par
    symbole pour un ordre stable d'une exécution à l'autre) plus la liste
    biocarburants/gaz renouvelables ci-dessus. L'ordre stable est
    indispensable pour que la rotation par jour de l'année
    (`_pick_daily_companies`) porte sur des tranches différentes à chaque
    exécution, pas un ordre qui varie selon l'état du moteur SQL."""
    tracked = db.execute(select(Security.symbol, Security.name).order_by(Security.symbol)).all()
    companies = [{"company_name": row.name, "symbol": row.symbol} for row in tracked]
    companies += [{"company_name": name, "symbol": None} for name in BIOFUEL_RENEWABLE_GAS_COMPANIES]
    return companies


def _pick_daily_companies(db: Session, n: int = COMPANIES_PER_RUN) -> list[dict]:
    """Rotation déterministe sans état à mémoriser nulle part (même principe
    que `agents/jane_veille.py:_pick_weekly_topic`) : le jour de l'année
    choisit la tranche de `n` entreprises, donc l'univers complet est couvert
    en environ `len(_all_companies()) / n` jours sans avoir besoin de suivre
    "la dernière entreprise traitée" en base. Tranche circulaire (module la
    longueur de la liste) : le jour où la tranche chevauche la fin de la
    liste, elle reprend au début plutôt que de renvoyer moins de `n`
    entreprises ce jour-là."""
    companies = _all_companies(db)
    if not companies:
        return []
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    start = (day_of_year * n) % len(companies)
    return [companies[(start + i) % len(companies)] for i in range(min(n, len(companies)))]


def collect_company_news(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """`scope` doit contenir `company_name` (et `symbol` si c'est un titre
    suivi — sert à la fois de scope de dédup/lecture dans
    `company_news_knowledge` et de FK valide pour `AgentEvent.symbol`
    lorsqu'il est renseigné ; les entreprises biocarburants/gaz renouvelables
    n'en ont pas, `symbol=None`).

    Recherche Tavily + synthèse multi-sources Mistral en un seul appel —
    même discipline "accurate" que `agents/jane_veille.py:collect_veille_web`
    (voir sa docstring) : les résultats indépendants sont fournis ensemble,
    le prompt système (`agents/prompts/george_veille_system.txt`) priorise
    ce qui est confirmé par plusieurs sources et signale les désaccords/faits
    à source unique. Aucun résultat Tavily (clé absente, service en échec,
    rien trouvé) renvoie une liste vide plutôt qu'une erreur — cette fonction
    est censée tourner sans supervision via un job planifié."""
    if not scope or not scope.get("company_name"):
        raise ValueError("La collecte 'actualites_entreprise' requiert 'company_name' dans le périmètre.")

    company_name = scope["company_name"]
    symbol = scope.get("symbol")
    # "perspectives économiques secteur contrats" ajouté à la requête de
    # base, demandé directement par l'utilisateur pour que la veille couvre
    # plus que la seule actualité de résultats bruts — même enrichissement
    # que celui appliqué au repli web de `agents/chat.py`.
    query = f"{company_name} actualités résultats financiers perspectives économiques secteur contrats"
    results = web_search.search(query, max_results=RESULTS_PER_COMPANY)
    if not results:
        return []

    sources_payload = json.dumps(
        [{"titre": r["titre"], "extrait": r["extrait"], "url": r["url"]} for r in results],
        ensure_ascii=False,
    )
    system_prompt = mistral_client.load_system_prompt("george_veille_system.txt")
    summary = mistral_client.complete(system_prompt, sources_payload, model=mistral_client.MODEL_SMALL)

    source_name = f"Recherche web ({len(results)} sources) — {company_name}"
    entry = company_knowledge.add_company_knowledge(
        db, content=summary, company_name=company_name, symbol=symbol, source_name=source_name, source_url=results[0]["url"]
    )
    observed_at = entry.created_at.isoformat() if entry is not None else datetime.now(timezone.utc).isoformat()
    status_note = ADDED_STATUS_NOTE if entry is not None else DUPLICATE_STATUS_NOTE

    label = f"Veille entreprise — {company_name} ({status_note})"
    item = CollectedItem(
        label=label,
        value=summary,
        unit=None,
        source_name=source_name,
        source_url=results[0]["url"],
        observed_at=observed_at,
        symbol=symbol,
    )
    return [(label, [item])]


def run(company: str | None = None) -> dict:
    """Point d'entrée réutilisable — extrait du bloc `__main__` d'origine
    (octobre 2026) pour être appelé à la fois en CLI
    (`.github/workflows/daily_george_veille.yml`, désormais en secours
    manuel seulement) et depuis `POST /cron/george-veille`
    (`api/routers/cron.py`), ajouté quand les minutes GitHub Actions
    gratuites du dépôt ont été épuisées plusieurs semaines de suite —
    contredit le choix "jamais via l'endpoint HTTP" documenté plus haut
    dans ce fichier, gardé comme trace de la raison d'origine (priorité
    basse) plutôt qu'effacé, mais ce n'est plus la pratique actuelle.

    `company` reproduit l'argument CLI positionnel : une chaîne vide ou
    `None` déclenche la rotation quotidienne (`_pick_daily_companies`), un
    nom explicite résout son `symbol` depuis `securities` s'il existe."""
    import logging

    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    engine = get_engine()
    session_factory = get_session_factory()

    with session_factory() as db:
        if company:
            match = db.execute(select(Security.symbol).where(Security.name == company)).first()
            companies = [{"company_name": company, "symbol": match.symbol if match else None}]
        else:
            companies = _pick_daily_companies(db)

        total_added, total_duplicates, total_failed = 0, 0, 0
        for item_company in companies:
            try:
                result = run_collection_task(db, engine, "actualites_entreprise", collect_company_news, item_company)
            except Exception:  # noqa: BLE001 -- une entreprise en erreur ne doit jamais interrompre les suivantes
                logging.exception("Échec de la veille pour « %s » -- entreprise sautée.", item_company["company_name"])
                db.rollback()
                total_failed += 1
                continue
            is_duplicate = bool(result["validated"]) and f"({DUPLICATE_STATUS_NOTE})" in result["validated"][0].description
            if is_duplicate:
                total_duplicates += 1
            elif result["validated"]:
                total_added += 1
            logging.info(
                "%s : %s",
                item_company["company_name"],
                DUPLICATE_STATUS_NOTE if is_duplicate else (ADDED_STATUS_NOTE if result["validated"] else "aucun résultat web"),
            )

    return {"added": total_added, "duplicates": total_duplicates, "failed": total_failed, "total": len(companies)}


if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.INFO)
    cli_company = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    cli_summary = run(cli_company)
    print(
        f"{cli_summary['added']} entrée(s) ajoutée(s), {cli_summary['duplicates']} quasi-doublon(s) ignoré(s), "
        f"{cli_summary['failed']} échec(s) sur {cli_summary['total']} entreprise(s)."
    )
