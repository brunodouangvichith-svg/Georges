"""Ingestion du positionnement spéculatif (CFTC, rapport "TFF — Futures
Only") par devise, pour le score de saturation du panier Carry Trade (ad
hoc, pas une phase du roadmap). API Socrata publique et sans clé, vérifiée
en direct avant l'écriture de ce fichier (dernière ligne réelle pour le yen
japonais datée du 2026-07-28, `open_interest_all=432366`).

Seules les devises de financement des paires suivies (`ingestion.carry_pairs
.CARRY_PAIRS`) sont interrogées : c'est sur elles que se mesure
l'encombrement du trade (ex. "short JPY" est le côté surpeuplé d'un carry
JPY-financé), pas sur les devises cibles. `CFTC_CONTRACT_NAMES` couvre
cependant les 7 devises ayant un vrai contrat futures CFTC (le dollar
américain n'en a pas — c'est la devise de facturation de la plupart des
contrats FX, jamais elle-même un contrat), au cas où une future paire
utiliserait une autre devise de financement.

Publication hebdomadaire (vendredi, position du mardi précédent) — un
rafraîchissement quotidien suffit largement.

Usage :
    python -m ingestion.cot_positioning
"""

import datetime
import logging

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.carry_pairs import CARRY_PAIRS
from ingestion.db import get_engine
from ingestion.models import CotPositioning

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 2

CFTC_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"

# Nom du contrat CFTC ("TFF — Futures Only") par devise — le dollar
# américain n'a pas d'entrée, ce n'est jamais lui-même un contrat listé.
CFTC_CONTRACT_NAMES = {
    "JPY": "JAPANESE YEN",
    "AUD": "AUSTRALIAN DOLLAR",
    "GBP": "BRITISH POUND",
    "CHF": "SWISS FRANC",
    "MXN": "MEXICAN PESO",
    "NZD": "NEW ZEALAND DOLLAR",
    "EUR": "EURO FX",
}


def _get_with_retry(params: dict) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(CFTC_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, params, exc)
    return None


def fetch_cot_positioning(currency: str) -> dict | None:
    """Dernier rapport COT disponible pour `currency`. `None` (jamais
    d'exception) si la devise n'a pas de contrat CFTC connu, si la requête
    échoue, ou si la réponse est vide."""
    contract_name = CFTC_CONTRACT_NAMES.get(currency)
    if contract_name is None:
        logger.warning("Aucun contrat CFTC connu pour la devise %s", currency)
        return None

    response = _get_with_retry(
        {
            "$where": f"contract_market_name='{contract_name}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 1,
        }
    )
    if response is None:
        return None
    rows = response.json()
    if not rows:
        logger.warning("Aucune ligne COT pour %s (%s)", currency, contract_name)
        return None
    row = rows[0]
    return {
        "report_date": datetime.date.fromisoformat(row["report_date_as_yyyy_mm_dd"][:10]),
        "lev_money_long": int(row["lev_money_positions_long"]),
        "lev_money_short": int(row["lev_money_positions_short"]),
        "open_interest_all": int(row["open_interest_all"]),
    }


def run() -> dict[str, bool]:
    engine = get_engine()
    funding_currencies = sorted({funding for _, _, funding, _ in CARRY_PAIRS})
    results: dict[str, bool] = {}
    for currency in funding_currencies:
        fetched = fetch_cot_positioning(currency)
        if fetched is None:
            results[currency] = False
            continue
        with engine.begin() as conn:
            stmt = pg_insert(CotPositioning).values(
                currency=currency,
                report_date=fetched["report_date"],
                lev_money_long=fetched["lev_money_long"],
                lev_money_short=fetched["lev_money_short"],
                open_interest_all=fetched["open_interest_all"],
                source_name="CFTC (TFF)",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[CotPositioning.currency, CotPositioning.report_date],
                set_={
                    "lev_money_long": stmt.excluded.lev_money_long,
                    "lev_money_short": stmt.excluded.lev_money_short,
                    "open_interest_all": stmt.excluded.open_interest_all,
                    "source_name": stmt.excluded.source_name,
                },
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
