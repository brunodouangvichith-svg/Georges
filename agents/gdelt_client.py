"""Client pour l'API GDELT v2 DOC (gratuite, sans clé) — recherche
d'articles par mot-clé, en complément de `agents/web_search.py` (Tavily)
dans `agents/geopolitical_veille.py`. Porté depuis un projet sœur de
l'utilisateur (Wchecks, `clients/gdelt_client.py`), mais délibérément SANS
son mécanisme de scraping (`clients/article_scraper.py`, `requests`+
`BeautifulSoup` sur chaque URL) : ce projet n'a jamais ajouté de scraping
site-spécifique, préférant Tavily précisément pour éviter d'avoir à écrire/
maintenir ce genre de code (voir `agents/jane_veille.py`, section sur
pourquoi Playwright/Scrapy n'a jamais été ajouté).

**Limite acceptée, pas contournée** : la Doc API GDELT (mode `ArtList`) ne
renvoie que titre/URL/date/langue/pays-source par article, jamais le texte
de la page — Wchecks compensait en scrapant chaque URL pour obtenir un
extrait réel. Ici, chaque résultat n'a donc qu'un `titre` et un `url`,
`extrait` toujours vide — un signal plus pauvre qu'un résultat Tavily, mais
un vrai titre d'article réel reste une information exploitable pour Mistral
(voir `agents/prompts/geopolitical_veille_system.txt`, dont les règles
gèrent déjà le cas d'un fait à source unique/peu détaillé). Contrairement à
Wchecks (recherche globale par catégorie, pays résolu APRÈS coup depuis
`sourcecountry` du média), ce client scope directement la recherche par
pays (le nom du pays est un terme de la requête, en ET logique avec les
mots-clés) — évite d'avoir à porter `mapping/country_mapping.py`
(résolution de pays par nom/domaine) juste pour ça.

Pas de traduction ici (contrairement à `translate_batch` chez Wchecks, qui
utilise Gemini) : Mistral synthétise directement à partir des titres, dans
n'importe quelle langue d'origine, comme il le fait déjà pour les extraits
Tavily potentiellement non francophones."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 8

# Mots-clés de recherche (correspondance de texte littérale, pas de concept
# — voir la mise en garde de Wchecks contre des synonymes trop génériques
# qui noieraient le signal sous du bruit) fusionnant les 3 dimensions
# distinctes de Wchecks (conflits énergétiques, tensions sociales, activité
# militaire) en une seule liste : George fait une veille géopolitique/
# économique généraliste par pays, pas 3 flux séparés.
KEYWORDS = [
    "oil", "pipeline", "sanctions", "war", "attack on infrastructure",
    "protest", "strike", "riot", "social unrest",
    "drone strike", "missile test", "military drill",
]

# GDELT ne couvre que des sources anglophones ici (`sourcelang: english`),
# alors que `country` vient de `whitelist_journaux.json` en français (ex.
# "Allemagne", "Chine (officiel)") — sans traduction, le terme de requête ne
# matche quasiment jamais un article anglophone et la recherche revient vide
# pour la plupart des 77 pays. Ne couvre que les 77 pays de la whitelist,
# volontairement (voir mapping/country_mapping.py chez Wchecks pour un
# mapping plus large, pas porté ici — inutile hors de ce périmètre).
GDELT_COUNTRY_NAMES = {
    "Afrique du Sud": "South Africa", "Algérie": "Algeria", "Allemagne": "Germany",
    "Angola": "Angola", "Arabie saoudite": "Saudi Arabia", "Argentine": "Argentina",
    "Australie": "Australia", "Azerbaïdjan": "Azerbaijan", "Bangladesh": "Bangladesh",
    "Belgique": "Belgium", "Brésil": "Brazil", "Cameroun": "Cameroon", "Canada": "Canada",
    "Chili": "Chile", "Chine (Hong Kong)": "Hong Kong", "Chine (officiel)": "China",
    "Colombie": "Colombia", "Corée du Nord": "North Korea", "Corée du Sud": "South Korea",
    "Costa Rica": "Costa Rica", "Cuba": "Cuba", "Curaçao / Aruba / Saint-Martin": "Curacao",
    "Côte d'Ivoire": "Ivory Coast", "Espagne": "Spain", "France": "France", "Grèce": "Greece",
    "Guatemala": "Guatemala", "Inde": "India", "Indonésie": "Indonesia", "Iran": "Iran",
    "Israël": "Israel", "Italie": "Italy", "Jamaïque": "Jamaica", "Japon": "Japan",
    "Kazakhstan": "Kazakhstan", "Kenya": "Kenya", "Kirghizistan": "Kyrgyzstan",
    "Liban": "Lebanon", "Libye": "Libya", "Maroc": "Morocco", "Mexique": "Mexico",
    "Nigeria": "Nigeria", "Norvège": "Norway", "Nouvelle-Zélande": "New Zealand",
    "Ouzbékistan": "Uzbekistan", "Pakistan": "Pakistan", "Panama": "Panama",
    "Pays-Bas": "Netherlands", "Philippines": "Philippines", "Pologne": "Poland",
    "Porto Rico": "Puerto Rico", "Portugal": "Portugal", "Pérou": "Peru",
    "Royaume-Uni": "United Kingdom", "Russie": "Russia", "République dominicaine": "Dominican Republic",
    "Salvador": "El Salvador", "Singapour": "Singapore", "Soudan": "Sudan",
    "Sri Lanka": "Sri Lanka", "Suisse": "Switzerland", "Syrie": "Syria", "Sénégal": "Senegal",
    "Tadjikistan": "Tajikistan", "Taïwan": "Taiwan", "Thaïlande": "Thailand",
    "Tunisie": "Tunisia", "Turkménistan": "Turkmenistan", "Turquie": "Turkey",
    "Ukraine": "Ukraine", "Uruguay": "Uruguay", "Venezuela": "Venezuela",
    "Vietnam": "Vietnam", "Yémen": "Yemen", "Égypte": "Egypt",
    "Émirats arabes unis": "United Arab Emirates", "États-Unis": "United States",
}


def _get_with_retry(params: dict) -> dict | None:
    """Même politique que `clients/gdelt_client.py` chez Wchecks : un 429
    est un rate-limit attendu sur cette API partagée (pas une erreur à
    remonter), retenté avec pause plutôt qu'abandonné immédiatement."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.warning("GDELT injoignable (tentative %d/%d) : %s", attempt, MAX_RETRIES, exc)
            return None
        if response.status_code == 429:
            logger.warning("GDELT rate-limit (429), tentative %d/%d, pause %ds", attempt, MAX_RETRIES, RETRY_BACKOFF_SECONDS)
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.warning("Erreur GDELT : %s", exc)
            return None
        try:
            return response.json()
        except ValueError:
            logger.warning("Réponse GDELT non-JSON (probablement vide) : %s", response.text[:200])
            return None
    logger.warning("GDELT injoignable après %d tentatives (rate-limit persistant).", MAX_RETRIES)
    return None


def search_articles(country: str, max_records: int = 10, timespan: str = "7d") -> list[dict]:
    """Articles GDELT mentionnant `country` ET au moins un mot-clé de
    `KEYWORDS`, sur les `timespan` derniers jours. Retourne une liste de
    `{"titre", "extrait", "url"}` — même forme que `agents.web_search.search`,
    pour pouvoir être concaténée directement avec ses résultats (voir
    `agents/geopolitical_veille.py:collect_geopolitical_news`). `extrait`
    est toujours `""` (voir docstring du module). Liste vide si la requête
    échoue ou ne trouve rien — jamais d'exception, même éthique que le
    reste de ce projet (`agents/web_search.py`, `agents/collectors/*.py`).

    `country` (nom français, ex. "Allemagne") est traduit vers son
    équivalent anglais via `GDELT_COUNTRY_NAMES` pour le terme de requête
    (voir docstring de ce dict) — repli sur `country` tel quel si absent du
    mapping, plutôt qu'un échec, même éthique tolérante que le reste du
    projet face à une entrée non reconnue."""
    query_country = GDELT_COUNTRY_NAMES.get(country, country)
    query = f'"{query_country}" (' + " OR ".join(f'"{kw}"' if " " in kw else kw for kw in KEYWORDS) + ")"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "timespan": timespan,
        "sourcelang": "english",
    }

    payload = _get_with_retry(params)
    if payload is None:
        return []

    articles = payload.get("articles", [])
    results = [
        {"titre": article.get("title", ""), "extrait": "", "url": article["url"]}
        for article in articles
        if article.get("url")
    ]
    logger.info("gdelt_client.search_articles(%r) : %d article(s) trouvé(s)", country, len(results))
    return results
