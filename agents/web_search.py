"""Recherche web réelle pour Jane (`agents/jane.py:ask`) quand sa base de
connaissances indexée (`jane_knowledge`) ne couvre pas la question posée —
demandé directement par l'utilisateur, ad hoc, pas une phase du roadmap.

Via Tavily (tavily.com), choisi pour son tier gratuit et parce qu'il est
pensé spécifiquement pour ce cas d'usage : résultats déjà nettoyés
(titre/extrait/URL), pas de scraping HTML à écrire ici. Même discipline que
le reste de `agents/`/`ingestion/` (voir `agents/collectors/macro.py`) :
la recherche est un appel HTTP simple et déterministe — Jane ne fait que
résumer des résultats déjà récupérés, jamais une recherche décidée par le
LLM lui-même.

`search()` ne lève jamais silencieusement dans le vide : `TAVILY_API_KEY`
absente renvoie une liste vide (repli optionnel, même convention que
`DEEPSEEK_API_KEY` dans `mistral_client.py`) ; un échec réseau/API réel lève
`WebSearchUnavailableError`, à charge de l'appelant de décider si c'est
bloquant ou non (dans `agents/jane.py:ask`, ce n'est pas le cas — une
recherche web ratée dégrade simplement vers "pas de résultats web", elle ne
fait jamais échouer toute la réponse de Jane)."""
import os

import httpx

TAVILY_API_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5


class WebSearchUnavailableError(RuntimeError):
    """Clé API manquante en usage direct, ou service Tavily injoignable/en
    erreur. `agents/jane.py:ask` traite cette exception comme "pas de
    résultats web" plutôt que de la laisser remonter — voir sa docstring."""


def search(query: str, max_results: int = MAX_RESULTS, days: int | None = None) -> list[dict]:
    """Retourne une liste de `{"titre", "extrait", "url"}`. Liste vide si
    `TAVILY_API_KEY` n'est pas configurée — le repli web est alors
    silencieusement ignoré, comme pour `DEEPSEEK_API_KEY`.

    `days` (optionnel) restreint aux actualités des N derniers jours (paramètres
    Tavily `topic="news"` + `days`) — utilisé par le rapport stratégique
    hebdomadaire, qui ne doit pas citer un article vieux de six mois comme une
    nouvelle de la semaine. Sans `days`, la requête est inchangée."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    payload = {"api_key": api_key, "query": query, "max_results": max_results}
    if days is not None:
        payload.update({"topic": "news", "days": days})
    try:
        response = httpx.post(
            TAVILY_API_URL,
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {"titre": item.get("title", ""), "extrait": item.get("content", ""), "url": item.get("url", "")}
            for item in data.get("results", [])
        ]
    except Exception as err:  # noqa: BLE001 — échec réseau/API/parsing/forme inattendue, tous traités pareil
        raise WebSearchUnavailableError(f"Recherche web Tavily indisponible : {err}") from err
