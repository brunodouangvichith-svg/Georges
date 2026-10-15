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
    python -m ingestion.bond_yields
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


def fetch_bond_yield(series_id: str) -> tuple[float, datetime.date] | None:
    """Dernière observation numérique de la série FRED `series_id`. `None`
    (jamais d'exception) en cas d'échec réseau ou d'absence d'observation
    exploitable — même éthique "log + skip" que le reste du projet."""
    response = _get_with_retry(series_id)
    if response is None:
        return None
    rows = list(csv.DictReader(io.StringIO(response.text)))
    for row in reversed(rows):
        value = row.get(series_id, ".")
        if value not in (".", "", None):
            return float(value), datetime.date.fromisoformat(row["observation_date"])
    logger.warning("Aucune observation numérique pour la série FRED %s", series_id)
    return None


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
        value_pct, observed_at = fetched
        with engine.begin() as conn:
            stmt = pg_insert(BondYieldSnapshot).values(
                instrument=instrument,
                value_pct=value_pct,
                observed_at=observed_at,
                source_name="FRED",
                source_url=f"{FRED_URL}?id={series_id}",
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
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok = [i for i, v in summary.items() if v]
    failed = [i for i, v in summary.items() if not v]
    print(f"{len(ok)}/{len(summary)} instruments mis à jour. Échecs : {failed or 'aucun'}")
