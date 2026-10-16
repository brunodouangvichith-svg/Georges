"""Ingestion des rendements obligataires souverains pour Obligataire Watch
(ad hoc, pas une phase du roadmap) — FRED, même endpoint/format que
`agents/collectors/macro.py:fetch_fred_series` (CSV public, sans clé, colonne
valeur nommée d'après l'ID de série exact, jamais générique "DATE"/"VALUE").

Vérification des 4 séries, limitée par le réseau de la session où ce module
a été écrit (proxy sortant bloquant `fred.stlouisfed.org` — voir
`docs/DATA_SOURCES.md`) :
- `IRLTLT01FRM156N` (OAT France 10 ans) : **déjà vérifiée en production**,
  utilisée depuis des mois par `agents/collectors/macro.py`.
- `DGS10` (Treasury US 10 ans) et `IRLTLT01DEM156N` (Bund Allemagne 10 ans,
  même famille OCDE que la série France) : confirmées réelles par recherche
  externe, jamais appelées en direct depuis cette session.
- `DGS2` (Treasury US 2 ans) : convention de nommage FRED standard (même
  famille que DGS10), **non confirmée indépendamment** — priorité n°1 à
  vérifier au premier run réel (CI ou Render).

Swap EUR 10 ans et OAT France 2/5 ans : aucune source gratuite fiable
identifiée, volontairement absents de `BOND_YIELD_SERIES` plutôt que
remplacés par une estimation (voir `docs/DATA_SOURCES.md`).

Usage :
    python -m ingestion.bond_yields                 # dernière valeur de chaque série
    python -m ingestion.bond_yields --backfill [10] # rattrapage de l'historique (années)

`run()` ne collecte que la dernière observation publiée : lancé seul sur une
base vide, le graphique n'a qu'un point par série et les variations 24h/7j/30j
restent "n/d". `backfill_history()` charge en une fois tout l'historique FRED
des N dernières années (même CSV, mêmes séries, même upsert idempotent) —
à lancer une fois après la création des tables, ou après un trou de collecte.
"""

from __future__ import annotations

import csv
import datetime
import io
import logging

import requests
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

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
DEFAULT_BACKFILL_YEARS = 10
# ~2 600 observations pour 10 ans de série quotidienne : quelques lots
# plutôt qu'un INSERT géant ou 2 600 allers-retours vers Supabase.
UPSERT_BATCH_SIZE = 500

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# (instrument, série FRED) — voir le docstring du module pour le détail de
# ce qui a (et n'a pas) pu être vérifié en direct avant l'écriture de ce fichier.
BOND_YIELD_SERIES = [
    (BOND_INSTRUMENT_OAT_FR_10Y, "IRLTLT01FRM156N"),
    (BOND_INSTRUMENT_BUND_DE_10Y, "IRLTLT01DEM156N"),
    (BOND_INSTRUMENT_UST_US_10Y, "DGS10"),
    (BOND_INSTRUMENT_UST_US_2Y, "DGS2"),
]


def _get_with_retry(series_id: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(FRED_URL, params={"id": series_id}, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, series_id, exc)
    return None


def parse_fred_csv(text: str, series_id: str) -> list[tuple[float, datetime.date]]:
    """Toutes les observations numériques du CSV FRED, dans l'ordre du
    fichier (chronologique). Les valeurs manquantes (".") et les lignes
    illisibles sont ignorées, jamais converties en 0."""
    observations: list[tuple[float, datetime.date]] = []
    for row in csv.DictReader(io.StringIO(text)):
        value = row.get(series_id, ".")
        if value in (".", "", None):
            continue
        try:
            observations.append((float(value), datetime.date.fromisoformat(row["observation_date"])))
        except (KeyError, TypeError, ValueError):
            continue
    return observations


def fetch_bond_yield(series_id: str) -> tuple[float, datetime.date] | None:
    """Dernière observation numérique de la série FRED `series_id`. `None`
    (jamais d'exception) en cas d'échec réseau ou d'absence d'observation
    exploitable — même éthique "log + skip" que le reste du projet."""
    response = _get_with_retry(series_id)
    if response is None:
        return None
    observations = parse_fred_csv(response.text, series_id)
    if not observations:
        logger.warning("Aucune observation numérique pour la série FRED %s", series_id)
        return None
    return observations[-1]


def fetch_bond_yield_history(series_id: str, since: datetime.date) -> list[tuple[float, datetime.date]] | None:
    """Observations de `series_id` datées de `since` ou après. `None` en cas
    d'échec réseau (à distinguer d'une liste vide : série joignable mais sans
    observation sur la période)."""
    response = _get_with_retry(series_id)
    if response is None:
        return None
    return [(value, observed_at) for value, observed_at in parse_fred_csv(response.text, series_id) if observed_at >= since]


def _upsert_snapshots(conn, instrument: str, series_id: str, observations: list[tuple[float, datetime.date]]) -> None:
    """Upsert idempotent sur (instrument, observed_at), par lots — même
    contrainte unique que la collecte quotidienne, donc relancer le
    rattrapage ne crée jamais de doublon."""
    for start in range(0, len(observations), UPSERT_BATCH_SIZE):
        batch = observations[start : start + UPSERT_BATCH_SIZE]
        stmt = pg_insert(BondYieldSnapshot).values(
            [
                {
                    "instrument": instrument,
                    "value_pct": value_pct,
                    "observed_at": observed_at,
                    "source_name": "FRED",
                    "source_url": f"{FRED_URL}?id={series_id}",
                }
                for value_pct, observed_at in batch
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[BondYieldSnapshot.instrument, BondYieldSnapshot.observed_at],
            set_={
                "value_pct": stmt.excluded.value_pct,
                "source_name": stmt.excluded.source_name,
                "source_url": stmt.excluded.source_url,
            },
        )
        conn.execute(stmt)


def backfill_history(years: int = DEFAULT_BACKFILL_YEARS) -> dict[str, int | None]:
    """Charge l'historique FRED des `years` dernières années pour les 4
    séries suivies. Renvoie `{instrument: nb d'observations écrites}`, `None`
    pour une série injoignable (les autres continuent). Ne journalise pas de
    ligne dans `bond_collection_runs` : ce n'est pas une collecte quotidienne,
    et le tableau de bord affiche la date de la dernière collecte réelle."""
    since = datetime.date.today() - datetime.timedelta(days=round(365.25 * years))
    engine = get_engine()
    written: dict[str, int | None] = {}
    for instrument, series_id in BOND_YIELD_SERIES:
        observations = fetch_bond_yield_history(series_id, since)
        if observations is None:
            logger.warning("Rattrapage impossible pour %s (%s) : série injoignable", instrument, series_id)
            written[instrument] = None
            continue
        with engine.begin() as conn:
            _upsert_snapshots(conn, instrument, series_id, observations)
        written[instrument] = len(observations)
    return written


def run() -> dict[str, bool]:
    """Collecte les 4 instruments suivis, journalise l'exécution dans
    `bond_collection_runs` (visibilité des erreurs demandée par le cahier
    des charges §17.7) et upsert chaque résultat dans `bond_yield_snapshots`.
    Renvoie `{instrument: succès}`."""
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

    results: dict[str, bool] = {}
    errors: list[str] = []
    for instrument, series_id in BOND_YIELD_SERIES:
        fetched = fetch_bond_yield(series_id)
        if fetched is None:
            results[instrument] = False
            errors.append(f"{instrument} ({series_id}) : aucune donnée récupérée")
            continue
        with engine.begin() as conn:
            _upsert_snapshots(conn, instrument, series_id, [fetched])
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
                error_summary="; ".join(errors) if errors else None,
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
            print(f"{instrument} : {'série injoignable' if count is None else f'{count} observation(s)'}")
        sys.exit(0 if all(count is not None for count in written.values()) else 1)
    summary = run()
    ok = [i for i, v in summary.items() if v]
    failed = [i for i, v in summary.items() if not v]
    print(f"{len(ok)}/{len(summary)} instruments mis à jour. Échecs : {failed or 'aucun'}")
