"""Calcule le score Carry Trade de chaque paire suivie depuis la base et
l'affiche (ad hoc, pas une phase du roadmap).

La formule est implémentée (sans accès DB) dans
`engine/carry_index.py:compute_carry_score`.

Usage :
    python -m engine.compute_carry_index
"""

import pandas as pd
from sqlalchemy import select

from engine.carry_index import compute_carry_score
from ingestion.db import get_engine
from ingestion.models import CarryRateSnapshot, CotPositioning, CurrencyPair, FxPriceOHLCV


def load_fx_prices(engine, symbol: str) -> pd.DataFrame:
    """Même forme que `engine.run_detection.load_prices`, mais sur
    `fx_prices_ohlcv`."""
    stmt = (
        select(
            FxPriceOHLCV.ts,
            FxPriceOHLCV.open,
            FxPriceOHLCV.high,
            FxPriceOHLCV.low,
            FxPriceOHLCV.close,
            FxPriceOHLCV.volume,
        )
        .where(FxPriceOHLCV.symbol == symbol)
        .order_by(FxPriceOHLCV.ts)
    )
    df = pd.read_sql(stmt, engine, index_col="ts")
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": "int64"})
    # Filtre une éventuelle dernière bougie NaN (séance en cours à
    # l'ingestion) — même correctif que `engine.run_detection.load_prices`,
    # voir sa docstring pour le bug réel que ça a causé en aval.
    return df[df["close"].notna()]


def latest_rate_by_currency(engine) -> dict[str, float]:
    with engine.begin() as conn:
        rows = conn.execute(
            select(CarryRateSnapshot.currency, CarryRateSnapshot.rate_pct, CarryRateSnapshot.observed_at).order_by(
                CarryRateSnapshot.currency, CarryRateSnapshot.observed_at.desc()
            )
        ).all()
    latest: dict[str, float] = {}
    for row in rows:
        latest.setdefault(row.currency, float(row.rate_pct))  # 1re ligne rencontrée par devise = la plus récente
    return latest


def latest_cot_by_currency(engine) -> dict[str, dict]:
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                CotPositioning.currency,
                CotPositioning.report_date,
                CotPositioning.lev_money_long,
                CotPositioning.lev_money_short,
                CotPositioning.open_interest_all,
            ).order_by(CotPositioning.currency, CotPositioning.report_date.desc())
        ).all()
    latest: dict[str, dict] = {}
    for row in rows:
        latest.setdefault(
            row.currency,
            {
                "lev_money_long": row.lev_money_long,
                "lev_money_short": row.lev_money_short,
                "open_interest_all": row.open_interest_all,
            },
        )
    return latest


def run() -> dict[str, dict]:
    """Renvoie le score de chaque paire de `currency_pairs`, par symbole."""
    engine = get_engine()
    with engine.begin() as conn:
        pairs = conn.execute(
            select(CurrencyPair.symbol, CurrencyPair.name, CurrencyPair.funding_currency, CurrencyPair.target_currency)
        ).all()

    rates = latest_rate_by_currency(engine)
    cot = latest_cot_by_currency(engine)

    results = {}
    for pair in pairs:
        fx_prices = load_fx_prices(engine, pair.symbol)
        results[pair.symbol] = {
            "name": pair.name,
            "funding_currency": pair.funding_currency,
            "target_currency": pair.target_currency,
            **compute_carry_score(
                funding_rate_pct=rates.get(pair.funding_currency),
                target_rate_pct=rates.get(pair.target_currency),
                fx_prices=fx_prices if not fx_prices.empty else None,
                cot=cot.get(pair.funding_currency),
            ),
        }
    return results


if __name__ == "__main__":
    for symbol, score in run().items():
        print(f"{symbol:12s} {score['name']:35s} carry={score['carry_pct']} vol={score['realized_vol_pct']} "
              f"ratio={score['carry_vol_ratio']} cot={score['cot_crowding_score']} -> {score['decision']}")
