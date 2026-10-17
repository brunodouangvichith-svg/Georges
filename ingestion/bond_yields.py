"""Ingestion des rendements obligataires souverains pour Obligataire Watch
(ad hoc, pas une phase du roadmap).

Sources, par instrument, dans l'ordre d'essai :

- **OAT France 10 ans** : TEC10 de la Banque de France (taux de l'échéance
  constante 10 ans, **quotidien**), via l'API Webstat — jeu `observations`,
  série `FM.D.FR.EUR.FR2.BB.FRMOYTEC10.HSTA`, champs `time_period` /
  `obs_value` (vérifiés en direct le 17/10/2026 ; `obs_value` vaut `null` les
  jours sans cotation). Exige une clé gratuite (`WEBSTAT_API_KEY`, en-tête
  `Authorization: Apikey …`) : sans elle, repli sur FRED.
- **Bund Allemagne 10 ans** : Bundesbank (rendement des titres fédéraux à 10
  ans, **quotidien**, sans clé), série BBSIS
  `D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A`, CSV `;` à virgule
  décimale (vérifié en direct le 16/10/2026 : 3,48 % au 16/10).
- **Repli** pour ces deux-là : FRED `IRLTLT01FRM156N` / `IRLTLT01DEM156N`
  (OCDE, **mensuel**, plusieurs semaines de retard) — l'ancienne source
  unique, qui faisait afficher une OAT du 1er septembre à mi-octobre.
- **Treasuries US 10 ans / 2 ans** : FRED `DGS10` / `DGS2` (quotidien).

Règles d'écriture (`bond_yield_snapshots`, unique sur (instrument, date)) :
- une source **principale** (quotidienne) écrit toutes ses observations de la
  fenêtre récupérée et, sur cette même fenêtre, retire les lignes d'une autre
  source (typiquement les moyennes mensuelles FRED datées du 1er) pour que la
  courbe et les variations ne mélangent pas deux définitions ;
- une source de **repli** n'écrit que sa dernière observation, et seulement
  si la date est libre : elle ne remplace jamais une valeur quotidienne.

Usage :
    python -m ingestion.bond_yields                 # collecte quotidienne (35 derniers jours)
    python -m ingestion.bond_yields --backfill [10] # rattrapage de l'historique (années)

La collecte quotidienne récupère les 35 derniers jours de chaque source
principale (idempotent) : les variations 24h/7j/30j sont donc disponibles dès
le premier passage, et un jour de collecte manqué se rattrape tout seul.
Le `--backfill` charge l'historique complet (ex. 10 ans) une fois.
"""

from __future__ import annotations

import csv
import datetime
import io
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass

import requests
from sqlalchemy import and_, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_UST_US_10Y,
    BOND_INSTRUMENT_UST_US_2Y,
    BondCollectionRun,
    BondYieldSnapshot,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2
DEFAULT_BACKFILL_YEARS = 10
DAILY_WINDOW_DAYS = 35
# Fenêtre au-delà de laquelle on passe des requêtes « dernières valeurs »
# (rapides) aux requêtes d'historique complet.
RECENT_QUERY_MAX_DAYS = 60
# ~2 600 observations pour 10 ans de série quotidienne : quelques lots
# plutôt qu'un INSERT géant ou 2 600 allers-retours vers Supabase.
UPSERT_BATCH_SIZE = 500

Observation = tuple[float, datetime.date]

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
WEBSTAT_DATASET_URL = "https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/observations"
WEBSTAT_TEC10_SERIES = "FM.D.FR.EUR.FR2.BB.FRMOYTEC10.HSTA"
WEBSTAT_SERIES_PAGE = "https://webstat.banque-france.fr/"  # portail ; la série est citée dans le docstring
BUNDESBANK_BUND10_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"
)

_DATE_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2});([^;]*)")


def _get_with_retry(url: str, *, params: dict | None = None, headers: dict | None = None, label: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, label, exc)
    return None


# ------------------------------------------------------------------ FRED


def parse_fred_csv(text: str, series_id: str) -> list[Observation]:
    """Toutes les observations numériques du CSV FRED, dans l'ordre du
    fichier (chronologique). Les valeurs manquantes (".") et les lignes
    illisibles sont ignorées, jamais converties en 0."""
    observations: list[Observation] = []
    for row in csv.DictReader(io.StringIO(text)):
        value = row.get(series_id, ".")
        if value in (".", "", None):
            continue
        try:
            observations.append((float(value), datetime.date.fromisoformat(row["observation_date"])))
        except (KeyError, TypeError, ValueError):
            continue
    return observations


def fetch_bond_yield_history(series_id: str, since: datetime.date) -> list[Observation] | None:
    """Observations FRED de `series_id` datées de `since` ou après. `None` en
    cas d'échec réseau (à distinguer d'une liste vide : série joignable mais
    sans observation sur la période)."""
    response = _get_with_retry(FRED_URL, params={"id": series_id}, label=f"FRED {series_id}")
    if response is None:
        return None
    return [(value, observed_at) for value, observed_at in parse_fred_csv(response.text, series_id) if observed_at >= since]


def fetch_bond_yield(series_id: str) -> Observation | None:
    """Dernière observation numérique de la série FRED `series_id` (`None` si
    rien d'exploitable)."""
    response = _get_with_retry(FRED_URL, params={"id": series_id}, label=f"FRED {series_id}")
    if response is None:
        return None
    observations = parse_fred_csv(response.text, series_id)
    if not observations:
        logger.warning("Aucune observation numérique pour la série FRED %s", series_id)
        return None
    return observations[-1]


# ------------------------------------------------------- Banque de France


def webstat_api_key() -> str | None:
    """Lue à l'appel (pas à l'import), comme les autres clés du projet."""
    key = os.environ.get("WEBSTAT_API_KEY", "").strip()
    return key or None


def parse_webstat_records(payload) -> list[Observation]:
    """Observations d'une réponse Webstat (`records` : `{"results": [...]}`,
    `exports/json` : `[...]`), triées par date. `obs_value` nul (jour sans
    cotation) ou illisible : ignoré."""
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    observations: list[Observation] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        value, period = row.get("obs_value"), row.get("time_period")
        if value is None or not period:
            continue
        try:
            observations.append((float(value), datetime.date.fromisoformat(str(period)[:10])))
        except (TypeError, ValueError):
            continue
    observations.sort(key=lambda obs: obs[1])
    return observations


def fetch_webstat_history(series_key: str, since: datetime.date) -> list[Observation] | None:
    """Observations Webstat de `series_key` depuis `since`. `None` sans clé
    `WEBSTAT_API_KEY` ou en cas d'échec (le repli prend le relais)."""
    key = webstat_api_key()
    if key is None:
        logger.info("WEBSTAT_API_KEY absente : Banque de France ignorée pour %s", series_key)
        return None
    headers = {"Authorization": f"Apikey {key}"}
    where = f'series_key="{series_key}"'
    if (datetime.date.today() - since).days <= RECENT_QUERY_MAX_DAYS:
        url = f"{WEBSTAT_DATASET_URL}/records"
        params = {"where": where, "order_by": "time_period desc", "limit": 100, "select": "time_period,obs_value"}
    else:
        url = f"{WEBSTAT_DATASET_URL}/exports/json"
        params = {"where": where, "select": "time_period,obs_value"}
    response = _get_with_retry(url, params=params, headers=headers, label=f"Webstat {series_key}")
    if response is None:
        return None
    try:
        payload = response.json()
    except ValueError:
        logger.warning("Réponse Webstat illisible pour %s", series_key)
        return None
    return [obs for obs in parse_webstat_records(payload) if obs[1] >= since]


# ------------------------------------------------------------- Bundesbank


def parse_bundesbank_csv(text: str) -> list[Observation]:
    """Lignes `AAAA-MM-JJ;3,48;` du CSV Bundesbank (en-têtes et commentaires
    ignorés, virgule décimale, valeur absente = ligne ignorée), triées."""
    observations: list[Observation] = []
    for line in text.splitlines():
        match = _DATE_LINE.match(line.strip())
        if not match:
            continue
        raw = match.group(2).strip().replace(",", ".")
        if raw in ("", ".", "-"):
            continue
        try:
            observations.append((float(raw), datetime.date.fromisoformat(match.group(1))))
        except ValueError:
            continue
    observations.sort(key=lambda obs: obs[1])
    return observations


def fetch_bundesbank_history(url: str, since: datetime.date) -> list[Observation] | None:
    params: dict = {"format": "csv"}
    if (datetime.date.today() - since).days <= RECENT_QUERY_MAX_DAYS:
        params["lastNObservations"] = 60
    else:
        params["startPeriod"] = since.isoformat()
    response = _get_with_retry(url, params=params, label="Bundesbank")
    if response is None:
        return None
    return [obs for obs in parse_bundesbank_csv(response.text) if obs[1] >= since]


# ---------------------------------------------------------------- sources


@dataclass(frozen=True)
class BondSource:
    name: str
    url: str  # affichée dans l'app / le bulletin — jamais de clé dedans
    fetch_history: Callable[[datetime.date], list[Observation] | None]
    daily: bool  # source principale quotidienne (fait autorité sur sa fenêtre)


def _fred(series_id: str, daily: bool) -> BondSource:
    return BondSource(
        name="FRED" if daily else "FRED (OCDE, mensuel)",
        url=f"{FRED_URL}?id={series_id}",
        fetch_history=lambda since: fetch_bond_yield_history(series_id, since),
        daily=daily,
    )


BANQUE_DE_FRANCE_TEC10 = BondSource(
    name="Banque de France (TEC10)",
    url=WEBSTAT_SERIES_PAGE,
    fetch_history=lambda since: fetch_webstat_history(WEBSTAT_TEC10_SERIES, since),
    daily=True,
)
BUNDESBANK_BUND10 = BondSource(
    name="Bundesbank",
    url=BUNDESBANK_BUND10_URL,
    fetch_history=lambda since: fetch_bundesbank_history(BUNDESBANK_BUND10_URL, since),
    daily=True,
)

# (instrument, sources dans l'ordre d'essai)
BOND_YIELD_SERIES: list[tuple[str, list[BondSource]]] = [
    (BOND_INSTRUMENT_OAT_FR_10Y, [BANQUE_DE_FRANCE_TEC10, _fred("IRLTLT01FRM156N", daily=False)]),
    (BOND_INSTRUMENT_BUND_DE_10Y, [BUNDESBANK_BUND10, _fred("IRLTLT01DEM156N", daily=False)]),
    (BOND_INSTRUMENT_UST_US_10Y, [_fred("DGS10", daily=True)]),
    (BOND_INSTRUMENT_UST_US_2Y, [_fred("DGS2", daily=True)]),
]


# --------------------------------------------------------------- écriture


def _upsert_snapshots(conn, instrument: str, source: BondSource, observations: list[Observation], *, overwrite: bool = True) -> None:
    """Upsert par lots sur (instrument, observed_at). `overwrite=False` (repli)
    : n'écrit que les dates libres, ne remplace jamais une valeur existante."""
    for start in range(0, len(observations), UPSERT_BATCH_SIZE):
        batch = observations[start : start + UPSERT_BATCH_SIZE]
        stmt = pg_insert(BondYieldSnapshot).values(
            [
                {
                    "instrument": instrument,
                    "value_pct": value_pct,
                    "observed_at": observed_at,
                    "source_name": source.name,
                    "source_url": source.url,
                }
                for value_pct, observed_at in batch
            ]
        )
        if overwrite:
            stmt = stmt.on_conflict_do_update(
                index_elements=[BondYieldSnapshot.instrument, BondYieldSnapshot.observed_at],
                set_={
                    "value_pct": stmt.excluded.value_pct,
                    "source_name": stmt.excluded.source_name,
                    "source_url": stmt.excluded.source_url,
                },
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[BondYieldSnapshot.instrument, BondYieldSnapshot.observed_at])
        conn.execute(stmt)


def _write(conn, instrument: str, source: BondSource, observations: list[Observation]) -> None:
    """Applique les règles d'écriture du docstring du module."""
    if not observations:
        return
    if source.daily:
        first, last = observations[0][1], observations[-1][1]
        conn.execute(
            delete(BondYieldSnapshot).where(
                and_(
                    BondYieldSnapshot.instrument == instrument,
                    BondYieldSnapshot.observed_at >= first,
                    BondYieldSnapshot.observed_at <= last,
                    BondYieldSnapshot.source_name != source.name,
                )
            )
        )
        _upsert_snapshots(conn, instrument, source, observations)
    else:
        _upsert_snapshots(conn, instrument, source, observations[-1:], overwrite=False)


def _collect(instrument: str, sources: list[BondSource], since: datetime.date) -> tuple[BondSource, list[Observation]] | None:
    for source in sources:
        observations = source.fetch_history(since)
        if observations:
            return source, sorted(observations, key=lambda obs: obs[1])
        logger.warning("%s : rien depuis %s, source suivante", instrument, source.name)
    return None


def backfill_history(years: int = DEFAULT_BACKFILL_YEARS) -> dict[str, int | None]:
    """Charge l'historique des `years` dernières années, source principale
    d'abord. Renvoie `{instrument: nb d'observations écrites}`, `None` si
    aucune source n'a répondu. Pas de ligne dans `bond_collection_runs`."""
    since = datetime.date.today() - datetime.timedelta(days=round(365.25 * years))
    engine = get_engine()
    written: dict[str, int | None] = {}
    for instrument, sources in BOND_YIELD_SERIES:
        collected = _collect(instrument, sources, since)
        if collected is None:
            written[instrument] = None
            continue
        source, observations = collected
        if not source.daily:
            # Repli mensuel en rattrapage : tout l'historique, sans écraser.
            with engine.begin() as conn:
                _upsert_snapshots(conn, instrument, source, observations, overwrite=False)
        else:
            with engine.begin() as conn:
                _write(conn, instrument, source, observations)
        written[instrument] = len(observations)
    return written


def run() -> dict[str, bool]:
    """Collecte quotidienne des 4 instruments, journalisée dans
    `bond_collection_runs`. Renvoie `{instrument: succès}`. Un passage par la
    source de repli reste un succès mais est noté dans `error_summary`."""
    engine = get_engine()
    started_at = datetime.datetime.now(datetime.timezone.utc)
    with engine.begin() as conn:
        run_id = conn.execute(
            BondCollectionRun.__table__.insert()
            .values(
                started_at=started_at,
                status="running",
                instruments_requested=len(BOND_YIELD_SERIES),
                instruments_succeeded=0,
            )
            .returning(BondCollectionRun.id)
        ).scalar_one()

    since = datetime.date.today() - datetime.timedelta(days=DAILY_WINDOW_DAYS)
    results: dict[str, bool] = {}
    notes: list[str] = []
    for instrument, sources in BOND_YIELD_SERIES:
        collected = _collect(instrument, sources, since)
        if collected is None:
            results[instrument] = False
            notes.append(f"{instrument} : aucune source n'a répondu ({', '.join(s.name for s in sources)})")
            continue
        source, observations = collected
        if source is not sources[0]:
            notes.append(f"{instrument} : {sources[0].name} indisponible, repli sur {source.name}")
        with engine.begin() as conn:
            _write(conn, instrument, source, observations)
        results[instrument] = True

    succeeded = sum(1 for ok in results.values() if ok)
    status = "success" if succeeded == len(BOND_YIELD_SERIES) else ("partial" if succeeded > 0 else "failed")
    with engine.begin() as conn:
        conn.execute(
            BondCollectionRun.__table__.update()
            .where(BondCollectionRun.id == run_id)
            .values(
                finished_at=datetime.datetime.now(datetime.timezone.utc),
                status=status,
                instruments_succeeded=succeeded,
                error_summary="; ".join(notes) if notes else None,
            )
        )
    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        years = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BACKFILL_YEARS
        written = backfill_history(years)
        for instrument, count in written.items():
            print(f"{instrument} : {'aucune source joignable' if count is None else f'{count} observation(s)'}")
        sys.exit(0 if all(count is not None for count in written.values()) else 1)
    summary = run()
    ok = [i for i, v in summary.items() if v]
    failed = [i for i, v in summary.items() if not v]
    print(f"{len(ok)}/{len(summary)} instruments mis à jour. Échecs : {failed or 'aucun'}")
