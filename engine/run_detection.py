"""Exécute la détection de patterns sur tout l'univers (`securities`) et
insère les résultats dans `patterns_detected`.

Usage :
    python -m engine.run_detection
"""

import pandas as pd
from sqlalchemy import select

from engine.detect import detect_all
from ingestion.db import get_engine
from ingestion.models import PatternDetected, PriceOHLCV, Security


def load_prices(engine, symbol: str) -> pd.DataFrame:
    stmt = (
        select(
            PriceOHLCV.ts,
            PriceOHLCV.open,
            PriceOHLCV.high,
            PriceOHLCV.low,
            PriceOHLCV.close,
            PriceOHLCV.volume,
        )
        .where(PriceOHLCV.symbol == symbol)
        .order_by(PriceOHLCV.ts)
    )
    df = pd.read_sql(stmt, engine, index_col="ts")
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    return df.astype({"open": float, "high": float, "low": float, "close": float, "volume": "int64"})


def run() -> int:
    """Détecte les figures actives pour chaque titre et les insère dans
    `patterns_detected`. Renvoie le nombre de figures insérées."""
    engine = get_engine()
    with engine.begin() as conn:
        symbols = [row[0] for row in conn.execute(select(Security.symbol)).all()]

    inserted = 0
    for symbol in symbols:
        df = load_prices(engine, symbol)
        if df.empty:
            continue
        matches = detect_all(df)
        if not matches:
            continue
        with engine.begin() as conn:
            for match in matches:
                conn.execute(
                    PatternDetected.__table__.insert().values(
                        symbol=symbol,
                        pattern_type=match.pattern_type,
                        detected_at=match.detected_at,
                        confidence=match.confidence,
                        context=match.context,
                    )
                )
                inserted += 1
    return inserted


if __name__ == "__main__":
    count = run()
    print(f"{count} figures détectées et insérées dans patterns_detected.")
