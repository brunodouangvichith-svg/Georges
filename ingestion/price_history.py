"""Ingestion de l'historique de prix long terme via yfinance — ad hoc, pas une
phase du roadmap. Demandé directement par l'utilisateur pour disposer de
6 mois/1 an/3 ans/5 ans/10 ans de recul par titre, dans une table dédiée
(`price_history_long`), distincte de `prices_ohlcv` (qui ne garde que 2 ans,
la fenêtre utilisée par la détection de figures, Phase 1).

Une seule période est téléchargée et stockée (10 ans, la plus longue
demandée) plutôt que les 5 séparément : 10 ans contient déjà les 4 autres
durées, filtrables à la demande sur `ts` (`ts >= now - 6 mois`, etc.) plutôt
que dupliquées 5 fois pour les mêmes séances.

Réutilise `ingestion.ohlcv.download_symbol` (retry/backoff, tolérant aux
titres introuvables) pour le téléchargement — seule la table de destination
change.

Usage :
    python -m ingestion.price_history
"""

import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import PriceHistoryLong, Security
from ingestion.ohlcv import download_symbol

logger = logging.getLogger(__name__)

PERIOD = "10y"


def _to_aware(ts: pd.Timestamp):
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()


def upsert_price_history(engine, symbol: str, df: pd.DataFrame) -> int:
    """Insère/mets à jour les lignes de `df` dans `price_history_long`
    (upsert sur la clé (symbol, ts), sans danger à relancer plusieurs fois)."""
    if df.empty:
        return 0
    # yfinance renvoie parfois une ligne NaN (séance du jour incomplète,
    # cotation suspendue) : on ne l'écrit pas, sinon un NaN finit dans
    # `close` (colonne Numeric) et casse les calculs en aval.
    df = df.dropna(subset=["open", "high", "low", "close"])
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
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
        }
        for ts, row in df.iterrows()
    ]
    with engine.begin() as conn:
        stmt = pg_insert(PriceHistoryLong).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[PriceHistoryLong.symbol, PriceHistoryLong.ts],
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


def run(period: str = PERIOD) -> dict[str, int]:
    """Télécharge et charge l'historique long terme de tous les titres de
    `securities`. Renvoie, par symbole, le nombre de lignes chargées (ou -1
    en cas d'échec/ticker introuvable)."""
    engine = get_engine()
    with engine.begin() as conn:
        symbols = [row[0] for row in conn.execute(select(Security.symbol)).all()]

    results: dict[str, int] = {}
    for symbol in symbols:
        df = download_symbol(symbol, period=period)
        results[symbol] = upsert_price_history(engine, symbol, df) if df is not None else -1
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = run()
    ok = [s for s, v in summary.items() if v >= 0]
    failed = [s for s, v in summary.items() if v < 0]
    print(f"{len(ok)}/{len(summary)} titres mis à jour. Échecs : {failed or 'aucun'}")
