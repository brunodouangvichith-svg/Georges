"""Veille géopolitique/économique continue par pays pour George — "pilier 7"
de la roadmap (`George_Prompts_Claude_Code.md`, Phase 7), jusqu'ici jamais
implémenté malgré `whitelist_journaux.md`/`.json` déjà présents à la racine
du repo ("Not wired into any code yet"). Porté depuis un projet sœur de
l'utilisateur (Wchecks, veille énergétique/géopolitique indépendante) qui
avait construit un agent équivalent — mais réimplémenté ici selon les
conventions déjà établies dans CE projet, pas copié tel quel : Wchecks
scrape directement les pages d'accueil des journaux (`requests`+
`BeautifulSoup`), alors que George a délibérément écarté le scraping
site-spécifique au profit de la recherche Tavily + synthèse Mistral
multi-sources (voir `agents/jane_veille.py`, section sur pourquoi Playwright/
Scrapy n'a jamais été ajouté) — même discipline "accurate" que
`agents/george_veille.py:collect_company_news`, dont ce module est la copie
structurelle directe, juste scopée par pays plutôt que par entreprise (voir
`agents/geopolitical_knowledge.py`).

**GDELT, intégré à la même synthèse Mistral, pas une table séparée** —
demandé directement par l'utilisateur pour compléter Tavily (quelques
résultats choisis) par une vraie recherche systématique sur un flux
d'actualité mondial (voir `agents/gdelt_client.py`). `collect_geopolitical_news`
concatène les résultats Tavily et GDELT avant l'appel Mistral unique : les
deux sources se recoupent dans la même synthèse, gouvernée par les mêmes
règles anti-hallucination (`geopolitical_veille_system.txt`), plutôt que
deux flux parallèles à réconcilier ailleurs. GDELT est gratuit/sans clé
(pas de contrainte de budget comme Tavily) mais sa Doc API ne renvoie que
titre/URL par article (pas de texte de page, voir `agents/gdelt_client.py`
pour pourquoi ce n'est pas comblé par du scraping) — un signal plus pauvre
que Tavily mais un vrai titre réel reste exploitable par Mistral.

`whitelist_journaux.json` sert de liste de pays (et de noms de journaux de
référence injectés dans la requête Tavily pour la cibler) — PAS d'URL à
scraper : le champ `sites` du JSON n'est ici qu'un indice de recherche
supplémentaire, jamais fetché directement.

Budget Tavily (tier gratuit, 1000 requêtes/mois) : `agents/george_veille.py`
en consomme déjà ~900/mois (10 entreprises/jour x 3 résultats x ~30 jours,
voir sa docstring) et `agents/jane_veille.py:collect_veille_web` ~13/mois (1
sujet/semaine x 3 résultats) — marge restante estimée à ~85/mois. D'où une
cadence HEBDOMADAIRE (pas quotidienne) et RESULTS_PER_COUNTRY réduit à 2 (pas
3 comme les deux autres veilles) : COUNTRIES_PER_RUN (8) x 2 résultats x ~4.3
semaines/mois =~ 69 requêtes/mois, sous la marge restante avec une réserve.
Cette estimation vient du raisonnement documenté dans le code existant, pas
d'une vraie mesure du quota actuellement consommé (qui inclut aussi les
replis web réactifs de `agents/chat.py`/`agents/web_search.py`, imprévisibles)
— à vérifier dans le tableau de bord Tavily avant d'augmenter ces constantes.
À ce rythme, les 77 pays de la whitelist sont couverts en ~10 semaines.

Volontairement non enregistré dans `agents/collectors/__init__.py:COLLECTORS`
(donc pas joignable via `POST /agents/collect`) — même précédent que
`george_veille.py`/`collect_veille_web` : une veille de fond à faible
priorité, jamais via l'endpoint HTTP réactif. Tourne via
`.github/workflows/weekly_geopolitical_veille.yml`."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agents import gdelt_client, geopolitical_knowledge, mistral_client, web_search
from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

DEFAULT_WHITELIST_PATH = Path(__file__).resolve().parent.parent / "whitelist_journaux.json"

# 8 pays/semaine x 2 résultats =~ 69 requêtes Tavily/mois -- voir le budget
# détaillé dans la docstring du module avant de changer ces constantes.
COUNTRIES_PER_RUN = 8
RESULTS_PER_COUNTRY = 2

DUPLICATE_STATUS_NOTE = "quasi-doublon ignoré"
ADDED_STATUS_NOTE = "ajoutée à geopolitical_knowledge"

# Regroupement par région des 77 pays de whitelist_journaux.json — PAS issu
# de ce fichier lui-même (une seule table plate, sans colonne région) mais
# porté depuis le même projet sœur (Wchecks) qui avait déjà dû inventer
# cette taxonomie (6 zones) pour ranger ses propres données de référence.
# Sert à peupler `GeopoliticalKnowledge.region` (voir `_load_countries`) et
# le `scope["region"]` transmis à `collect_geopolitical_news`.
COUNTRY_TO_REGION = {
    "Afrique du Sud": "Afrique",
    "Algérie": "Afrique",
    "Allemagne": "Europe & UK",
    "Angola": "Afrique",
    "Arabie saoudite": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Argentine": "Amérique du Nord & Latine",
    "Australie": "Océanie",
    "Azerbaïdjan": "Europe de l'Est, Russie & Asie Centrale",
    "Bangladesh": "Asie",
    "Belgique": "Europe & UK",
    "Brésil": "Amérique du Nord & Latine",
    "Cameroun": "Afrique",
    "Canada": "Amérique du Nord & Latine",
    "Chili": "Amérique du Nord & Latine",
    "Chine (Hong Kong)": "Asie",
    "Chine (officiel)": "Asie",
    "Colombie": "Amérique du Nord & Latine",
    "Corée du Nord": "Asie",
    "Corée du Sud": "Asie",
    "Costa Rica": "Amérique du Nord & Latine",
    "Cuba": "Amérique du Nord & Latine",
    "Curaçao / Aruba / Saint-Martin": "Amérique du Nord & Latine",
    "Côte d'Ivoire": "Afrique",
    "Espagne": "Europe & UK",
    "France": "Europe & UK",
    "Grèce": "Europe & UK",
    "Guatemala": "Amérique du Nord & Latine",
    "Inde": "Asie",
    "Indonésie": "Asie",
    "Iran": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Israël": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Italie": "Europe & UK",
    "Jamaïque": "Amérique du Nord & Latine",
    "Japon": "Asie",
    "Kazakhstan": "Europe de l'Est, Russie & Asie Centrale",
    "Kenya": "Afrique",
    "Kirghizistan": "Europe de l'Est, Russie & Asie Centrale",
    "Liban": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Libye": "Afrique",
    "Maroc": "Afrique",
    "Mexique": "Amérique du Nord & Latine",
    "Nigeria": "Afrique",
    "Norvège": "Europe & UK",
    "Nouvelle-Zélande": "Océanie",
    "Ouzbékistan": "Europe de l'Est, Russie & Asie Centrale",
    "Pakistan": "Asie",
    "Panama": "Amérique du Nord & Latine",
    "Pays-Bas": "Europe & UK",
    "Philippines": "Asie",
    "Pologne": "Europe de l'Est, Russie & Asie Centrale",
    "Porto Rico": "Amérique du Nord & Latine",
    "Portugal": "Europe & UK",
    "Pérou": "Amérique du Nord & Latine",
    "Royaume-Uni": "Europe & UK",
    "Russie": "Europe de l'Est, Russie & Asie Centrale",
    "République dominicaine": "Amérique du Nord & Latine",
    "Salvador": "Amérique du Nord & Latine",
    "Singapour": "Asie",
    "Soudan": "Afrique",
    "Sri Lanka": "Asie",
    "Suisse": "Europe & UK",
    "Syrie": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Sénégal": "Afrique",
    "Tadjikistan": "Europe de l'Est, Russie & Asie Centrale",
    "Taïwan": "Asie",
    "Thaïlande": "Asie",
    "Tunisie": "Afrique",
    "Turkménistan": "Europe de l'Est, Russie & Asie Centrale",
    "Turquie": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Ukraine": "Europe de l'Est, Russie & Asie Centrale",
    "Uruguay": "Amérique du Nord & Latine",
    "Venezuela": "Amérique du Nord & Latine",
    "Vietnam": "Asie",
    "Yémen": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Égypte": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "Émirats arabes unis": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
    "États-Unis": "Amérique du Nord & Latine",
}


def _load_countries(path: Path = DEFAULT_WHITELIST_PATH) -> list[dict]:
    """Charge `whitelist_journaux.json` — liste de {country, language,
    outlets, sites} — et y ajoute `region` (voir `COUNTRY_TO_REGION`,
    `None` si un pays n'y figure pas — tolérant, jamais une exception pour
    ça). Triée par `country` dans le fichier lui-même (voir sa génération),
    donc un ordre stable d'une exécution à l'autre sans re-trier ici, même
    précondition que `_all_companies` (voir `agents/george_veille.py`) pour
    que la rotation hebdomadaire porte sur des tranches différentes à
    chaque exécution."""
    with path.open(encoding="utf-8") as f:
        countries = json.load(f)
    for country in countries:
        country["region"] = COUNTRY_TO_REGION.get(country["country"])
    return countries


def _pick_weekly_countries(countries: list[dict], n: int = COUNTRIES_PER_RUN) -> list[dict]:
    """Rotation déterministe sans état à mémoriser nulle part, même principe
    que `agents/jane_veille.py:_pick_weekly_topic` (numéro de semaine ISO)
    combiné à la rotation par tranche circulaire de
    `agents/george_veille.py:_pick_daily_companies` (ici par semaine plutôt
    que par jour, puisque cette veille est hebdomadaire) : la tranche de `n`
    pays choisie chevauche la fin de la liste et reprend au début plutôt que
    de renvoyer moins de `n` pays cette semaine-là."""
    if not countries:
        return []
    week_number = datetime.now(timezone.utc).isocalendar().week
    start = (week_number * n) % len(countries)
    return [countries[(start + i) % len(countries)] for i in range(min(n, len(countries)))]


def collect_geopolitical_news(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """`scope` doit contenir `country` (et optionnellement `region`,
    `outlets` — noms de journaux de référence utilisés pour cibler la
    recherche, jamais fetchés directement, voir docstring du module).

    Recherche Tavily + GDELT (voir `agents/gdelt_client.py`) + synthèse
    multi-sources Mistral en un seul appel — même discipline "accurate" que
    `agents/george_veille.py:collect_company_news` (voir sa docstring) : les
    résultats des deux sources sont fournis ENSEMBLE au même appel Mistral,
    le prompt système (`agents/prompts/geopolitical_veille_system.txt`)
    priorise ce qui est confirmé par plusieurs sources et signale les
    désaccords/faits à source unique. GDELT est gratuit (pas de garde-fou de
    quota nécessaire, contrairement à Tavily) et interrogé sans condition ;
    un échec de l'une ou l'autre source dégrade vers une liste vide pour
    cette source (jamais une exception, y compris pour Tavily dont
    `WebSearchUnavailableError` est ici attrapée pour respecter cette
    garantie) — seule l'absence des DEUX renvoie un groupe vide plutôt qu'une
    erreur, cette fonction étant censée tourner sans supervision via un job
    planifié."""
    if not scope or not scope.get("country"):
        raise ValueError("La collecte 'actualites_geopolitiques' requiert 'country' dans le périmètre.")

    country = scope["country"]
    region = scope.get("region")
    # Les noms des 1-2 premiers journaux de référence (whitelist) sont
    # ajoutés à la requête pour la cibler sur des sources sérieuses du pays,
    # sans jamais les fetcher directement (voir docstring du module).
    outlet_hint = " ".join(scope.get("outlets", [])[:2])
    query = f"{country} {outlet_hint} actualité économique géopolitique tensions sociales conflits"
    try:
        tavily_results = web_search.search(query, max_results=RESULTS_PER_COUNTRY)
    except web_search.WebSearchUnavailableError:
        logger.warning("Tavily indisponible pour « %s », repli sur GDELT seul.", country)
        tavily_results = []
    gdelt_results = gdelt_client.search_articles(country)
    results = tavily_results + gdelt_results
    if not results:
        return []

    sources_payload = json.dumps(
        [{"titre": r["titre"], "extrait": r["extrait"], "url": r["url"]} for r in results],
        ensure_ascii=False,
    )
    system_prompt = mistral_client.load_system_prompt("geopolitical_veille_system.txt")
    summary = mistral_client.complete(system_prompt, sources_payload, model=mistral_client.MODEL_SMALL)

    # "GDELT" n'apparaît que si des résultats GDELT ont effectivement
    # contribué -- sinon la mention mentirait sur la provenance réelle.
    source_label = "Recherche web + GDELT" if gdelt_results else "Recherche web"
    source_name = f"{source_label} ({len(results)} sources) — {country}"
    entry = geopolitical_knowledge.add_geopolitical_knowledge(
        db, content=summary, country=country, region=region, source_name=source_name, source_url=results[0]["url"]
    )
    observed_at = entry.created_at.isoformat() if entry is not None else datetime.now(timezone.utc).isoformat()
    status_note = ADDED_STATUS_NOTE if entry is not None else DUPLICATE_STATUS_NOTE

    label = f"Veille géopolitique — {country} ({status_note})"
    item = CollectedItem(
        label=label,
        value=summary,
        unit=None,
        source_name=source_name,
        source_url=results[0]["url"],
        observed_at=observed_at,
    )
    return [(label, [item])]


if __name__ == "__main__":
    import sys

    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    logging.basicConfig(level=logging.INFO)
    cli_engine = get_engine()
    cli_session_factory = get_session_factory()
    cli_all_countries = _load_countries()

    with cli_session_factory() as cli_db:
        # Même garde que `agents/george_veille.py` : le workflow GitHub
        # Actions passe toujours un argument, même vide sur une exécution
        # planifiée sans saisie manuelle.
        if len(sys.argv) > 1 and sys.argv[1]:
            cli_arg_country = sys.argv[1]
            cli_match = next((c for c in cli_all_countries if c["country"] == cli_arg_country), None)
            cli_countries = (
                [cli_match]
                if cli_match
                else [{"country": cli_arg_country, "outlets": [], "region": COUNTRY_TO_REGION.get(cli_arg_country)}]
            )
        else:
            cli_countries = _pick_weekly_countries(cli_all_countries)

        cli_total_added, cli_total_duplicates, cli_total_failed = 0, 0, 0
        for cli_country in cli_countries:
            cli_scope = {
                "country": cli_country["country"],
                "region": cli_country.get("region"),
                "outlets": cli_country.get("outlets", []),
            }
            try:
                cli_result = run_collection_task(cli_db, cli_engine, "actualites_geopolitiques", collect_geopolitical_news, cli_scope)
            except Exception:  # noqa: BLE001 -- un pays en erreur ne doit jamais interrompre les suivants
                logging.exception("Échec de la veille pour « %s » -- pays sauté.", cli_country["country"])
                cli_db.rollback()
                cli_total_failed += 1
                continue
            cli_is_duplicate = bool(cli_result["validated"]) and f"({DUPLICATE_STATUS_NOTE})" in cli_result["validated"][0].description
            if cli_is_duplicate:
                cli_total_duplicates += 1
            elif cli_result["validated"]:
                cli_total_added += 1
            logging.info(
                "%s : %s",
                cli_country["country"],
                DUPLICATE_STATUS_NOTE if cli_is_duplicate else (ADDED_STATUS_NOTE if cli_result["validated"] else "aucun résultat web"),
            )

    print(
        f"{cli_total_added} entrée(s) ajoutée(s), {cli_total_duplicates} quasi-doublon(s) ignoré(s), "
        f"{cli_total_failed} échec(s) sur {len(cli_countries)} pays."
    )
