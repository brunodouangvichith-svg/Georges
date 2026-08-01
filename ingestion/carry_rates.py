"""Ingestion des taux courts par devise pour le panier Carry Trade (ad hoc,
pas une phase du roadmap) — FRED, mêmes endpoint/format que
`agents/collectors/macro.py:fetch_fred_series` (CSV public, sans clé,
colonne valeur nommée d'après l'ID de série exact, jamais générique
"DATE"/"VALUE" — même piège déjà documenté). Sept séries vérifiées en
direct avant l'écriture de ce fichier : six "3-Month Interbank Rate" OCDE
(même famille que `IRLTLT01FRM156N` déjà utilisée pour l'OAT) plus le taux
de dépôt BCE (EUR) et le taux des Fed Funds (USD), plus directement suivis
et plus récents que leurs équivalents "interbancaire 3 mois".

Usage :
    python -m ingestion.carry_rates
"""

import csv
import datetime
import io
import logging

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import CarryRateSnapshot

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# (devise, série FRED) — vérifié en direct (200, dernière valeur non vide)
# pour chacune avant l'écriture de ce module.
CARRY_RATE_SERIES = [
    ("JPY", "IR3TIB01JPM156N"),
    ("MXN", "IR3TIB01MXM156N"),
    ("AUD", "IR3TIB01AUM156N"),
    ("NZD", "IR3TIB01NZM156N"),
    ("GBP", "IR3TIB01GBM156N"),
    ("CHF", "IR3TIB01CHM156N"),
    ("EUR", "ECBDFR"),
    ("USD", "FEDFUNDS"),
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


def fetch_carry_rate(currency: str, series_id: str) -> tuple[float, datetime.date] | None:
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
    logger.warning("Aucune observation numérique pour la série FRED %s (%s)", series_id, currency)
    return None


def run() -> dict[str, bool]:
    engine = get_engine()
    results: dict[str, bool] = {}
    for currency, series_id in CARRY_RATE_SERIES:
        fetched = fetch_carry_rate(currency, series_id)
        if fetched is None:
            results[currency] = False
            continue
        rate_pct, observed_at = fetched
        with engine.begin() as conn:
            stmt = pg_insert(CarryRateSnapshot).values(
                currency=currency, rate_pct=rate_pct, observed_at=observed_at, source_name="FRED"
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[CarryRateSnapshot.currency, CarryRateSnapshot.observed_at],
                set_={"rate_pct": stmt.excluded.rate_pct, "source_name": stmt.excluded.source_name},
            )
            conn.execute(stmt)
        results[currency] = True
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok = [c for c, v in summary.items() if v]
    failed = [c for c, v in summary.items() if not v]
    print(f"{len(ok)}/{len(summary)} devises mises à jour. Échecs : {failed or 'aucun'}")
