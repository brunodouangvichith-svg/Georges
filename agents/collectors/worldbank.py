"""Sous-agent de collecte "données World Bank" (Phase 7, extension) —
indicateurs macro France-spécifiques publics, sans clé API, en complément
de `macro.py` (OAT France + taux de change) et `eurostat.py` (chômage/
inflation zone euro, pas de détail par pays). Porté depuis un projet sœur
de l'utilisateur (Wchecks, `clients/worldbank_client.py`) qui interroge
l'API World Bank pour ~217 pays sans restriction de champ — ce module ne
reprend que le PARSING de la réponse (format `[métadonnées, données]`
vérifié en production dans ce projet sœur), pas son approche multi-pays :
`MacroIndicatorSnapshot` (voir `agents/orchestrator/run.py`) n'a pas de
colonne pays/`pays_code` — c'est une table à un instantané par indicateur
"global"/France, pas une table par pays comme `country_debt` chez
Wchecks. Élargir à d'autres pays demanderait une vraie colonne pays sur
`MacroIndicatorSnapshot`, un changement de schéma hors du périmètre de
cette extension.

Un seul appel HTTP par indicateur (`country/FRA/indicator/{code}`), une
fenêtre glissante de 10 ans (calculée à l'appel, jamais des bornes en dur —
`/code-review` a trouvé une première version figée sur "2015:2025" qui
aurait cessé de voir toute nouvelle publication passé 2025) pour retomber
sur la plus récente valeur non nulle en cas de publication tardive — même
éthique "remonter depuis la période la plus récente" que
`agents/collectors/eurostat.py:fetch_eurostat_series`. Source unique par
indicateur — aucune alternative publique sans clé identifiée pour ces
séries officielles, donc toujours `validated` à réputation 0.6 (voir
`agents/orchestrator/validation.py`), comme les autres indicateurs à
source unique de ce module.

`REQUEST_TIMEOUT_SECONDS`/`MAX_RETRIES` alignés sur `macro.py`/
`eurostat.py` (10s, pas les 30s de `clients/worldbank_client.py` chez
Wchecks) — `/code-review` a signalé qu'un timeout plus long, multiplié par
5 indicateurs synchrones dans `POST /agents/collect` (route `sync def`,
voir `api/routers/agents.py` — dimensionnée pour "quelques secondes", pas
pour bloquer un worker FastAPI plusieurs minutes), pouvait épuiser le pool
de threads sync sous requêtes concurrentes. Pire cas désormais 5 × 2 × 10s
= 100s, comparable au pire cas déjà accepté de `macro.py` (6 fetchs × 2 ×
10s = 120s), pas un nouveau risque isolé."""

from __future__ import annotations

import datetime
import logging

import requests

from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
YEARS_OF_HISTORY = 10

WORLDBANK_URL_TEMPLATE = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"

# (label, unité, code pays ISO3, code indicateur World Bank). Codes repris
# tels quels de config.WORLDBANK_INDICATORS chez Wchecks (déjà vérifiés en
# production dans ce projet sœur) : recettes fiscales (GC.TAX.TOTL.GD.ZS),
# chômage (SL.UEM.TOTL.ZS), inflation (FP.CPI.TOTL.ZG), budget défense
# (MS.MIL.XPND.GD.ZS), production industrielle (NV.IND.TOTL.ZS). La dette
# publique est délibérément omise ici : Wchecks lui-même est passé du code
# World Bank (GC.DOD.TOTL.GD.ZS) au FMI pour cet indicateur précis (voir
# `clients/worldbank_client.py`, en-tête de module) — pas de raison de
# reprendre une source que le projet d'origine a lui-même abandonnée pour
# cette donnée.
INDICATORS = [
    ("Recettes fiscales (France, % PIB)", "%", "FRA", "GC.TAX.TOTL.GD.ZS"),
    ("Taux de chômage (France, Banque mondiale)", "%", "FRA", "SL.UEM.TOTL.ZS"),
    ("Inflation (France, Banque mondiale)", "%", "FRA", "FP.CPI.TOTL.ZG"),
    ("Budget défense (France, % PIB)", "%", "FRA", "MS.MIL.XPND.GD.ZS"),
    ("Production industrielle (France, % PIB)", "%", "FRA", "NV.IND.TOTL.ZS"),
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


def fetch_worldbank_indicator(
    indicator_code: str, country: str, label: str, source_name: str, unit: str | None
) -> CollectedItem | None:
    """Réponse World Bank : liste `[métadonnées, données]` — `données` est
    une liste d'entrées `{"value", "countryiso3code", "date", ...}` triée
    du plus récent au plus ancien dans la pratique observée par Wchecks,
    mais reparcourue explicitement plutôt que supposée triée (`sorted` sur
    `date`) pour rester correct même si l'API change d'ordre. Renvoie
    `None` (jamais d'exception) si la requête échoue ou si aucune
    observation numérique n'est trouvée sur les 10 dernières années — même
    éthique "log + skip" que les autres fetchers de ce projet."""
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    date_range = f"{current_year - YEARS_OF_HISTORY}:{current_year}"
    url = WORLDBANK_URL_TEMPLATE.format(country=country, indicator=indicator_code)
    response = _get_with_retry(url, params={"format": "json", "per_page": 20, "date": date_range})
    if response is None:
        return None

    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        logger.warning("Réponse World Bank inattendue pour '%s' (%s) : %s", indicator_code, country, payload)
        return None

    entries = sorted(
        (e for e in payload[1] if e.get("value") is not None and e.get("date")),
        key=lambda e: e["date"],
        reverse=True,
    )
    if not entries:
        logger.warning("Aucune observation numérique pour l'indicateur World Bank %s (%s)", indicator_code, country)
        return None

    latest = entries[0]
    return CollectedItem(
        label=label,
        value=float(latest["value"]),
        unit=unit,
        source_name=source_name,
        source_url=f"{url}?date={latest['date']}",
        observed_at=latest["date"],
    )


def collect_donnees_worldbank(db, engine, scope=None) -> list[tuple[str, list[CollectedItem]]]:
    """Ignore `db`/`engine`/`scope` — porte toujours sur `INDICATORS` dans
    son ensemble, comme `collect_donnees_macro`/`collect_donnees_eurostat`.
    Un indicateur en échec est omis (log + skip), jamais de groupe vide."""
    groups = []
    for label, unit, country, indicator_code in INDICATORS:
        item = fetch_worldbank_indicator(indicator_code, country, label=label, source_name="Banque mondiale", unit=unit)
        if item is not None:
            groups.append((label, [item]))
        else:
            logger.warning("Échec de la collecte World Bank pour « %s » — indicateur ignoré ce cycle.", label)
    return groups
