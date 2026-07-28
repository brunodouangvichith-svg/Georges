"""Sous-agent de collecte "données macro" (Phase 7, MVP) — récupère des
indicateurs macroéconomiques publics, sans clé API : FRED (`fredgraph.csv`,
Réserve fédérale de Saint-Louis) et la BCE (Statistical Data Warehouse). Le
taux EUR/USD est récupéré des deux pour démontrer un vrai recoupement
multi-sources (`agents/orchestrator/validation.py`) — les valeurs sont
proches mais pas identiques en pratique, sans rien fabriquer. Le taux OAT
10 ans reste à une seule source (aucune alternative publique sans clé
trouvée)."""

from __future__ import annotations

import csv
import io
import logging

import requests

from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ECB_URL_TEMPLATE = "https://data-api.ecb.europa.eu/service/data/EXR/{key}"

# (label, unité, [(nom_source, type_fetcher, identifiant_série), ...])
INDICATORS = [
    ("Taux OAT 10 ans (France)", "%", [("FRED", "fred", "IRLTLT01FRM156N")]),
    ("Taux de change EUR/USD", None, [("FRED", "fred", "DEXUSEU"), ("BCE", "ecb", "D.USD.EUR.SP00.A")]),
]


def _get_with_retry(url: str, params: dict | None = None) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, url, exc)
    return None


def fetch_fred_series(series_id: str, label: str, source_name: str, unit: str | None) -> CollectedItem | None:
    """Endpoint CSV public de FRED, sans clé API. Colonnes du CSV :
    `observation_date` et une colonne portant le nom exact de la série
    (`series_id`) — pas de nom de colonne générique "DATE"/"VALUE", vérifié
    en direct contre l'API réelle (`fredgraph.csv?id=IRLTLT01FRM156N` a pour
    en-tête `observation_date,IRLTLT01FRM156N`). Renvoie `None` (jamais
    d'exception) si la requête échoue ou si la série n'a aucune observation
    numérique — même éthique "log + skip" que `ingestion/ohlcv.py`."""
    response = _get_with_retry(FRED_URL, params={"id": series_id})
    if response is None:
        return None
    rows = list(csv.DictReader(io.StringIO(response.text)))
    for row in reversed(rows):
        value = row.get(series_id, ".")
        if value not in (".", "", None):
            return CollectedItem(
                label=label,
                value=float(value),
                unit=unit,
                source_name=source_name,
                source_url=f"{FRED_URL}?id={series_id}",
                observed_at=row["observation_date"],
            )
    logger.warning("Aucune observation numérique pour la série FRED %s", series_id)
    return None


def fetch_ecb_series(key: str, label: str, source_name: str, unit: str | None) -> CollectedItem | None:
    """Endpoint public de la BCE (Statistical Data Warehouse), sans clé
    API. Même contrat que `fetch_fred_series` : `None` en cas d'échec,
    jamais d'exception."""
    url = ECB_URL_TEMPLATE.format(key=key)
    response = _get_with_retry(url, params={"lastNObservations": 1, "format": "csvdata"})
    if response is None:
        return None
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        logger.warning("Aucune observation pour la série BCE %s", key)
        return None
    row = rows[-1]
    return CollectedItem(
        label=label,
        value=float(row["OBS_VALUE"]),
        unit=unit,
        source_name=source_name,
        source_url=url,
        observed_at=row["TIME_PERIOD"],
    )


def collect_donnees_macro(db, engine, scope=None) -> list[tuple[str, list[CollectedItem]]]:
    """Ignore `db`/`engine`/`scope` — cette collecte porte toujours sur
    l'ensemble des indicateurs macro suivis (`INDICATORS`), pas sur un titre
    ou panier précis. Un indicateur dont toutes les sources ont échoué ce
    cycle est simplement omis (log + skip), plutôt que de produire un
    groupe vide qui ferait échouer `validate()`. Le dict de dispatch est
    construit ici (pas au niveau module) pour que les tests puissent
    monkeypatcher `fetch_fred_series`/`fetch_ecb_series` sur le module et
    voir l'effet — un dict figé au chargement du module capturerait les
    fonctions d'origine avant tout monkeypatch."""
    fetchers = {"fred": fetch_fred_series, "ecb": fetch_ecb_series}
    groups = []
    for label, unit, sources in INDICATORS:
        items = []
        for source_name, kind, series_id in sources:
            item = fetchers[kind](series_id, label=label, source_name=source_name, unit=unit)
            if item is not None:
                items.append(item)
        if items:
            groups.append((label, items))
        else:
            logger.warning("Toutes les sources ont échoué pour « %s » — indicateur ignoré ce cycle.", label)
    return groups
