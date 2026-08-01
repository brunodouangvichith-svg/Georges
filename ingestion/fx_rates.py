"""Ingestion des cours de change quotidiens via yfinance, pour le panier
Carry Trade (ad hoc, pas une phase du roadmap) — mirroir direct de
`ingestion/ohlcv.py`, seule différence : univers issu de `currency_pairs`
plutôt que `securities`, écriture dans `fx_prices_ohlcv` plutôt que
`prices_ohlcv`. `volume` est toujours 0 pour du FX spot (yfinance n'en
fournit pas de réel pour ces tickers).

Usage :
    python -m ingestion.fx_rates
"""

import logging
import time

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import CurrencyPair, FxPriceOHLCV

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
DEFAULT_PERIOD = "2y"


def download_symbol(symbol: str, period: str = DEFAULT_PERIOD) -> pd.DataFrame | None:
    """Télécharge l'historique quotidien de `symbol`. Renvoie `None` si le
    ticker est introuvable ou si toutes les tentatives ont échoué."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
        except Exception as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, symbol, exc)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        if raw is None or raw.empty:
            logger.warning("Tentative %s/%s : aucune donnée pour %s (ticker introuvable ?)", attempt, MAX_RETRIES, symbol)
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        return _normalize(raw)

    logger.error("Abandon pour %s après %s tentatives.", symbol, MAX_RETRIES)
    return None


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "ts"
    return df


def _to_aware(ts: pd.Timestamp):
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()


def upsert_fx_prices(engine, symbol: str, df: pd.DataFrame) -> int:
    """Insère/mets à jour les lignes de `df` dans `fx_prices_ohlcv` (upsert
    sur la clé (symbol, ts), sans danger à relancer plusieurs fois)."""
    if df.empty:
        return 0
    rows = [
        {
            "symbol": symbol,
            "ts": _to_aware(ts),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        }
        for ts, row in df.iterrows()
    ]
    with engine.begin() as conn:
        stmt = pg_insert(FxPriceOHLCV).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FxPriceOHLCV.symbol, FxPriceOHLCV.ts],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        conn.execute(stmt)
    return len(rows)


def run(period: str = DEFAULT_PERIOD) -> dict[str, int]:
    """Télécharge et charge l'historique de toutes les paires de
    `currency_pairs`. Renvoie, par symbole, le nombre de lignes chargées (ou
    -1 en cas d'échec/ticker introuvable)."""
    engine = get_engine()
    with engine.begin() as conn:
        symbols = [row[0] for row in conn.execute(select(CurrencyPair.symbol)).all()]

    results: dict[str, int] = {}
    for symbol in symbols:
        df = download_symbol(symbol, period=period)
        results[symbol] = upsert_fx_prices(engine, symbol, df) if df is not None else -1
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok = [s for s, v in summary.items() if v >= 0]
    failed = [s for s, v in summary.items() if v < 0]
    print(f"{len(ok)}/{len(summary)} paires mises à jour. Échecs : {failed or 'aucun'}")
