"""Ingestion quotidienne du marché de l'énergie via OilPriceAPI (ad hoc, pas
une phase du roadmap) — Brent, WTI, gaz naturel, et produits raffinés
(diesel, fioul domestique, essence). Vérifié en direct avant d'écrire ce
module (les 6 codes ci-dessous renvoient un vrai prix, pas une valeur
factice) : Brent 91,04$, WTI 84,67$, gaz naturel 2,75$/mmbtu, etc.

`OILPRICEAPI_KEY` est lue au moment de l'appel, jamais à l'import — même
principe que `MISTRAL_API_KEY`/`FINNHUB_API_KEY` (`agents/mistral_client.py`,
`agents/collectors/finnhub.py` avant son retrait), pour que ce module reste
importable/testable sans clé configurée.

Palier gratuit : 200 requêtes/mois après l'essai de 7 jours — 6 codes/jour
= ~180/mois, sous le plafond. Ne jamais ajouter de déclenchement manuel
répété à cette ingestion sans revoir ce budget.

Usage :
    python -m ingestion.energy_prices
"""

import datetime
import logging
import os
import time

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import EnergyPriceSnapshot

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

OILPRICEAPI_URL = "https://api.oilpriceapi.com/v1/prices/latest"

# code OilPriceAPI -> unité renvoyée par l'API (vérifiée en direct par code,
# pas supposée uniforme : barrel pour le brut, mmbtu pour le gaz, gallon
# pour les produits raffinés).
COMMODITY_CODES = [
    "BRENT_CRUDE_USD",
    "WTI_USD",
    "NATURAL_GAS_USD",
    "DIESEL_USD",
    "HEATING_OIL_USD",
    "GASOLINE_USD",
]


def fetch_price(code: str) -> dict | None:
    """Renvoie `{"price", "unit", "currency", "change_24h_pct", "observed_at"}`
    pour `code`, ou `None` après épuisement des tentatives ou si la clé API
    est absente — jamais d'exception, même éthique que les autres scripts
    d'ingestion (`ingestion/ohlcv.py`, `ingestion/fundamentals.py`)."""
    api_key = os.environ.get("OILPRICEAPI_KEY")
    if not api_key:
        logger.warning("Variable d'environnement OILPRICEAPI_KEY manquante — ingestion énergie ignorée.")
        return None

    headers = {"Authorization": f"Token {api_key}"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                OILPRICEAPI_URL, params={"by_code": code}, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, code, exc)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        payload = response.json()
        data = payload.get("data")
        if not data or "price" not in data:
            logger.warning("Réponse OilPriceAPI sans prix exploitable pour %s : %s", code, payload)
            return None

        return {
            "price": float(data["price"]),
            "unit": data.get("unit", ""),
            "currency": data.get("currency", "USD"),
            "change_24h_pct": (data.get("changes") or {}).get("24h", {}).get("percent"),
            "observed_at": data.get("as_of") or data.get("created_at"),
        }

    logger.error("Abandon pour %s après %s tentatives.", code, MAX_RETRIES)
    return None


def upsert_price(engine, code: str, data: dict, snapshot_date: datetime.date) -> None:
    observed_at = None
    if data["observed_at"]:
        observed_at = datetime.datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))

    row = {
        "commodity_code": code,
        "price": data["price"],
        "unit": data["unit"],
        "currency": data["currency"],
        "change_24h_pct": data["change_24h_pct"],
        "price_observed_at": observed_at,
        "snapshot_date": snapshot_date,
    }
    with engine.begin() as conn:
        stmt = pg_insert(EnergyPriceSnapshot).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=[EnergyPriceSnapshot.commodity_code, EnergyPriceSnapshot.snapshot_date],
            set_={
                "price": stmt.excluded.price,
                "unit": stmt.excluded.unit,
                "currency": stmt.excluded.currency,
                "change_24h_pct": stmt.excluded.change_24h_pct,
                "price_observed_at": stmt.excluded.price_observed_at,
            },
        )
        conn.execute(stmt)


def run() -> dict[str, bool]:
    """Ingeste le prix courant des 6 matières premières suivies. Renvoie,
    par code, `True`/`False` selon le succès."""
    engine = get_engine()
    snapshot_date = datetime.date.today()
    results: dict[str, bool] = {}
    for code in COMMODITY_CODES:
        data = fetch_price(code)
        if data is not None:
            upsert_price(engine, code, data, snapshot_date)
        results[code] = data is not None
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok = [c for c, v in summary.items() if v]
    failed = [c for c, v in summary.items() if not v]
    print(f"{len(ok)}/{len(summary)} matières premières mises à jour. Échecs : {failed or 'aucun'}.")
