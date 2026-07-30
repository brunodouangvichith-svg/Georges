"""Sous-agent de collecte "cotation Finnhub" (Phase 7, extension) —
cotation temps réel d'un titre via l'API Finnhub (https://finnhub.io),
qui nécessite une clé API gratuite (variable d'environnement
`FINNHUB_API_KEY`, lue au moment de l'appel et non à l'import — même
principe que `agents/mistral_client.py:_get_client`/
`ingestion/db.py:get_database_url()` — pour qu'importer ce module ne
nécessite pas de clé configurée). Contrairement à Mistral (appel
synchrone déclenché par l'utilisateur, qui mérite une erreur explicite),
une clé absente ici est traitée comme n'importe quel autre échec de
collecte : `None` + log, jamais d'exception — même éthique que
`agents/collectors/macro.py`.

Forme de réponse confirmée en direct une fois une clé obtenue :
`{"c","d","dp","h","l","o","pc","t"}`. **Confirmé aussi (risque identifié à
l'écriture, vérifié ensuite) : le palier gratuit de Finnhub ne couvre pas
Euronext Paris** — `GET /quote?symbol=TTE.PA` renvoie un vrai `403 Forbidden`
(pas un `200` avec `c: 0`), alors qu'un ticker américain (`AAPL`) fonctionne.
`fetch_finnhub_quote` traite les deux cas (403, ou `c` nul/absent) de la
même façon : `None` + log, jamais d'exception."""

from __future__ import annotations

import logging
import os

import requests

from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2

FINNHUB_URL = "https://finnhub.io/api/v1/quote"


def _get_with_retry(url: str, params: dict) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, url, exc)
    return None


def fetch_finnhub_quote(symbol: str, label: str, source_name: str, unit: str | None) -> CollectedItem | None:
    """Cotation actuelle (`c`, "current price") d'un symbole via Finnhub.
    Renvoie `None` (jamais d'exception) si `FINNHUB_API_KEY` est absente,
    si la requête échoue (y compris un `403` pour un symbole/marché non
    couvert par le palier gratuit — vérifié en direct sur `TTE.PA`), ou si
    la réponse ne contient pas de prix courant exploitable. **Ne renseigne
    jamais `CollectedItem.symbol`** : contrairement aux autres champs
    `symbol` de ce projet, `AgentEvent.symbol`/`CollectedInfoQuarantine.symbol`
    portent une contrainte de clé étrangère vers `securities.symbol` — un
    symbole Finnhub interrogé (ex. `AAPL`, hors univers CAC 40/Mid 60)
    ferait échouer l'écriture en base avec une violation de FK si on le
    renseignait ici (bug réel rencontré en testant en direct). Le symbole
    reste visible dans `label`, ce qui suffit à l'affichage."""
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        logger.warning("Variable d'environnement FINNHUB_API_KEY manquante — collecte Finnhub ignorée.")
        return None

    response = _get_with_retry(FINNHUB_URL, params={"symbol": symbol, "token": api_key})
    if response is None:
        return None
    payload = response.json()
    price = payload.get("c")
    if not price:
        logger.warning("Aucune cotation exploitable pour %s via Finnhub (réponse : %s)", symbol, payload)
        return None
    return CollectedItem(
        label=label,
        value=float(price),
        unit=unit,
        source_name=source_name,
        source_url=f"{FINNHUB_URL}?symbol={symbol}",
        observed_at=str(payload.get("t", "")),
    )


def collect_donnees_finnhub(db, engine, scope=None) -> list[tuple[str, list[CollectedItem]]]:
    """Exige `scope["symbol"]` — contrairement à `donnees_macro`/
    `donnees_eurostat` (portée fixe), cette collecte porte sur un titre
    précis, même contrat que `agents/collectors/synthesis.py` pour
    `report_id` : lève `ValueError` si absent, traduit en 400 par
    `api/routers/agents.py`."""
    if not scope or not scope.get("symbol"):
        raise ValueError("scope['symbol'] est requis pour task_type='donnees_finnhub'.")
    symbol = scope["symbol"]
    label = f"Cotation Finnhub ({symbol})"
    item = fetch_finnhub_quote(symbol, label=label, source_name="Finnhub", unit="€")
    if item is None:
        return []
    return [(label, [item])]
