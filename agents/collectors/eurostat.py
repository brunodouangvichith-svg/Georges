"""Sous-agent de collecte "données Eurostat" (Phase 7, extension) —
statistiques officielles de la zone euro publiques, sans clé API, en
complément de FRED (`agents/collectors/macro.py`, centré sur les séries
américaines/françaises). Format JSON-stat 2.0, pas un simple CSV comme
FRED/BCE : chaque requête doit fixer toutes les dimensions sauf `geo` et
`time` à une seule catégorie, puis décoder l'offset plat de `value` à
partir de `dimension.*.category.index` et `size` (ordre de `id`).
Source unique par indicateur — aucune alternative publique sans clé
identifiée pour ces séries officielles, donc toujours `validated` à
réputation 0.6 (voir `agents/orchestrator/validation.py`), comme le taux
OAT dans `macro.py`."""

from __future__ import annotations

import logging

import requests

from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2

EUROSTAT_URL_TEMPLATE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"

# (label, unité, dataset, géo-code "zone euro", paramètres de requête fixant
# toutes les autres dimensions). Le géo-code de la zone euro diffère par
# dataset — vérifié en direct : une_rt_m veut "EA21", prc_hicp_manr veut
# "EA20". Ne pas supposer un code unique valable partout.
INDICATORS = [
    (
        "Taux de chômage (zone euro)",
        "%",
        "une_rt_m",
        "EA21",
        {"s_adj": "SA", "sex": "T", "age": "TOTAL", "unit": "PC_ACT", "lang": "en"},
    ),
    (
        "Inflation HICP (zone euro)",
        "%",
        "prc_hicp_manr",
        "EA20",
        {"unit": "RCH_A", "coicop": "CP00", "lang": "en"},
    ),
]


def _get_with_retry(url: str, params: dict) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, url, exc)
    return None


def fetch_eurostat_series(
    dataset: str, geo_code: str, params: dict, label: str, source_name: str, unit: str | None
) -> CollectedItem | None:
    """Requête JSON-stat 2.0 sur un dataset Eurostat, avec `geo` non fixé
    dans `params` (toutes les autres dimensions le sont) pour pouvoir
    retrouver son index de catégorie. Renvoie `None` (jamais d'exception)
    si la requête échoue, si `geo_code` n'existe pas pour ce dataset, ou si
    aucune observation numérique n'est trouvée en remontant depuis la
    période la plus récente — même éthique "log + skip" que
    `agents/collectors/macro.py:fetch_fred_series`."""
    url = EUROSTAT_URL_TEMPLATE.format(dataset=dataset)
    response = _get_with_retry(url, params={**params, "format": "JSON"})
    if response is None:
        return None

    payload = response.json()
    dimensions = payload["dimension"]
    dim_ids = payload["id"]
    sizes = payload["size"]

    geo_index_map = dimensions["geo"]["category"]["index"]
    if geo_code not in geo_index_map:
        logger.warning("Code géo %s absent du dataset Eurostat %s", geo_code, dataset)
        return None
    geo_index = geo_index_map[geo_code]

    if dim_ids.index("geo") >= dim_ids.index("time"):
        # Décodage JSON-stat "row-major" valable uniquement si `geo`
        # précède `time` dans `id` (vérifié en direct sur les deux datasets
        # utilisés ici) — toutes les dimensions intermédiaires ont une
        # taille de 1 (fixées via `params`) donc ne pèsent pas dans
        # l'offset, mais l'ordre geo -> time doit être vérifié, pas supposé.
        logger.warning("Ordre de dimensions inattendu pour le dataset Eurostat %s (geo après time)", dataset)
        return None

    time_labels = {v: k for k, v in dimensions["time"]["category"]["index"].items()}
    time_size = sizes[dim_ids.index("time")]

    # `value` est un objet clé->valeur creux dans les deux datasets vérifiés
    # en direct (positions sans donnée simplement absentes) ; JSON-stat 2.0
    # autorise aussi une forme tableau dense — normalisée ici en dict pour
    # ne traiter qu'un seul cas.
    raw_values = payload["value"]
    values = raw_values if isinstance(raw_values, dict) else {str(i): v for i, v in enumerate(raw_values)}
    for time_index in range(time_size - 1, -1, -1):
        offset = geo_index * time_size + time_index
        key = str(offset)
        if key in values and values[key] is not None:
            return CollectedItem(
                label=label,
                value=float(values[key]),
                unit=unit,
                source_name=source_name,
                source_url=f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}&geo={geo_code}",
                observed_at=time_labels[time_index],
            )
    logger.warning("Aucune observation numérique pour le dataset Eurostat %s (%s)", dataset, geo_code)
    return None


def collect_donnees_eurostat(db, engine, scope=None) -> list[tuple[str, list[CollectedItem]]]:
    """Ignore `db`/`engine`/`scope` — porte toujours sur `INDICATORS` dans
    son ensemble, comme `collect_donnees_macro`. Un indicateur en échec est
    omis (log + skip), jamais de groupe vide."""
    groups = []
    for label, unit, dataset, geo_code, params in INDICATORS:
        item = fetch_eurostat_series(dataset, geo_code, params, label=label, source_name="Eurostat", unit=unit)
        if item is not None:
            groups.append((label, [item]))
        else:
            logger.warning("Échec de la collecte Eurostat pour « %s » — indicateur ignoré ce cycle.", label)
    return groups
