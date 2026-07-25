"""Calcule le George Index de chaque panier depuis la base et l'affiche.

La formule est documentée dans `engine/george_index.md` et implémentée
(sans accès DB) dans `engine/george_index.py:compute_george_index`.

Usage :
    python -m engine.compute_george_index
"""

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select

from engine.george_index import compute_george_index
from engine.run_detection import load_prices
from ingestion.db import get_engine
from ingestion.models import Basket, BasketSecurity, PatternDetected


def load_patterns(engine) -> pd.DataFrame:
    with engine.begin() as conn:
        rows = conn.execute(
            select(PatternDetected.symbol, PatternDetected.detected_at, PatternDetected.confidence)
        ).all()
    df = pd.DataFrame(rows, columns=["symbol", "detected_at", "confidence"])
    if not df.empty:
        df["detected_at"] = pd.to_datetime(df["detected_at"])
    return df


def run(as_of=None) -> dict[str, float | None]:
    """Renvoie le George Index de chaque panier, par nom. `None` si un
    panier n'a aucune figure active (voir `engine/george_index.md`)."""
    engine = get_engine()
    as_of = as_of or datetime.now(timezone.utc)

    with engine.begin() as conn:
        baskets = conn.execute(select(Basket.id, Basket.name)).all()
        links = conn.execute(select(BasketSecurity.basket_id, BasketSecurity.symbol, BasketSecurity.weight)).all()

    patterns = load_patterns(engine)
    symbols = {link.symbol for link in links}
    price_frames = {symbol: load_prices(engine, symbol) for symbol in symbols}
    price_frames = {symbol: df for symbol, df in price_frames.items() if not df.empty}

    results = {}
    for basket in baskets:
        basket_symbols = [
            (link.symbol, float(link.weight) if link.weight is not None else 1.0)
            for link in links
            if link.basket_id == basket.id
        ]
        results[basket.name] = compute_george_index(basket_symbols, patterns, price_frames, as_of)
    return results


if __name__ == "__main__":
    for name, index in run().items():
        print(f"{name:35s} {index if index is not None else 'n/a'}")
