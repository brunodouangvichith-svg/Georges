"""Ingestion quotidienne des données fondamentales/entreprise et des
dividendes via yfinance (ad hoc, pas une phase du roadmap) — même univers
que `ingestion.ohlcv` (tous les titres de `securities`).

- **Retry** : même politique que `ingestion/ohlcv.py` (jusqu'à
  ``MAX_RETRIES`` tentatives par titre, backoff linéaire).
- **Fondamentaux** : un instantané par (titre, jour d'exécution) — voir
  `ingestion/models.py:CompanyFundamentals` pour pourquoi c'est un
  historique accumulé plutôt qu'une ligne écrasée à chaque run.
- **Dividendes** : un versement par ligne, upsert idempotent sur
  (titre, date ex-dividende).

Usage :
    python -m ingestion.fundamentals
"""

import datetime
import logging
import time

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import CompanyFundamentals, Dividend, Security

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

_FUNDAMENTALS_FIELDS = {
    "sector": "sector",
    "industry": "industry",
    "country": "country",
    "currency": "currency",
    "exchange": "exchange",
    "long_name": "longName",
    "website": "website",
    "long_business_summary": "longBusinessSummary",
    "full_time_employees": "fullTimeEmployees",
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "dividend_yield": "dividendYield",
    "beta": "beta",
    "fifty_two_week_high": "fiftyTwoWeekHigh",
    "fifty_two_week_low": "fiftyTwoWeekLow",
}


def fetch_fundamentals(symbol: str) -> dict | None:
    """Renvoie les champs fondamentaux + `raw_info` (dict `.info` complet)
    pour `symbol`, ou `None` si toutes les tentatives échouent. `.info` est
    déjà une requête réseau unique côté yfinance (pas de téléchargement
    d'historique ici, contrairement à `download_symbol`)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:  # réseau, throttling yfinance, etc.
            logger.warning("Tentative %s/%s (fondamentaux) échouée pour %s : %s", attempt, MAX_RETRIES, symbol, exc)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        if not info:
            logger.warning("Tentative %s/%s : aucune info pour %s (ticker introuvable ?)", attempt, MAX_RETRIES, symbol)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        data = {field: info.get(key) for field, key in _FUNDAMENTALS_FIELDS.items()}
        data["raw_info"] = info
        return data

    logger.error("Abandon fondamentaux pour %s après %s tentatives.", symbol, MAX_RETRIES)
    return None


def fetch_dividends(symbol: str) -> list[tuple[datetime.date, float]] | None:
    """Renvoie l'historique des dividendes de `symbol` sous forme de
    `(date ex-dividende, montant)`, ou `None` si l'appel échoue. Une liste
    vide (titre sans dividende, ex. une biotech) est un résultat valide, pas
    un échec."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            dividends: pd.Series = yf.Ticker(symbol).dividends
        except Exception as exc:
            logger.warning("Tentative %s/%s (dividendes) échouée pour %s : %s", attempt, MAX_RETRIES, symbol, exc)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        return [(ts.date(), float(amount)) for ts, amount in dividends.items()]

    logger.error("Abandon dividendes pour %s après %s tentatives.", symbol, MAX_RETRIES)
    return None


def upsert_fundamentals(engine, symbol: str, data: dict, observed_at: datetime.date) -> None:
    row = {"symbol": symbol, "observed_at": observed_at, **data}
    with engine.begin() as conn:
        stmt = pg_insert(CompanyFundamentals).values(row)
        update_cols = {k: getattr(stmt.excluded, k) for k in row if k not in ("symbol", "observed_at")}
        stmt = stmt.on_conflict_do_update(
            index_elements=[CompanyFundamentals.symbol, CompanyFundamentals.observed_at],
            set_=update_cols,
        )
        conn.execute(stmt)


def upsert_dividends(engine, symbol: str, rows: list[tuple[datetime.date, float]]) -> int:
    if not rows:
        return 0
    values = [{"symbol": symbol, "ex_date": ex_date, "amount": amount} for ex_date, amount in rows]
    with engine.begin() as conn:
        stmt = pg_insert(Dividend).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Dividend.symbol, Dividend.ex_date],
            set_={"amount": stmt.excluded.amount},
        )
        conn.execute(stmt)
    return len(values)


def run() -> dict[str, dict]:
    """Ingeste fondamentaux + dividendes pour tous les titres de `securities`.
    Renvoie, par symbole, `{"fundamentals": bool, "dividends": int}` (nombre
    de versements upsertés, ou -1 si l'appel dividendes a échoué)."""
    engine = get_engine()
    with engine.begin() as conn:
        symbols = [row[0] for row in conn.execute(select(Security.symbol)).all()]

    observed_at = datetime.date.today()
    results: dict[str, dict] = {}
    for symbol in symbols:
        fundamentals = fetch_fundamentals(symbol)
        if fundamentals is not None:
            upsert_fundamentals(engine, symbol, fundamentals, observed_at)

        dividends = fetch_dividends(symbol)
        dividend_count = upsert_dividends(engine, symbol, dividends) if dividends is not None else -1

        results[symbol] = {"fundamentals": fundamentals is not None, "dividends": dividend_count}
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok_fundamentals = [s for s, v in summary.items() if v["fundamentals"]]
    failed_fundamentals = [s for s, v in summary.items() if not v["fundamentals"]]
    total_dividends = sum(v["dividends"] for v in summary.values() if v["dividends"] >= 0)
    print(
        f"Fondamentaux : {len(ok_fundamentals)}/{len(summary)} titres mis à jour. "
        f"Échecs : {failed_fundamentals or 'aucun'}."
    )
    print(f"Dividendes : {total_dividends} versements upsertés au total.")
