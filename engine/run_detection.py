"""Exécute la détection de patterns sur tout l'univers (`securities`) et
insère les résultats dans `patterns_detected`.

Le score de confiance heuristique de chaque détecteur (Phase 1) est
remplacé par la probabilité prédite par le modèle appris (Phase 2,
`engine/scoring.py`) quand celui-ci est disponible et que l'historique du
titre est suffisant ; sinon l'heuristique est conservée telle quelle — voir
la docstring de `engine.scoring.predict_confidence`.

Usage :
    python -m engine.run_detection
"""

import pandas as pd
from sqlalchemy import select

from engine.detect import detect_all
from engine.scoring import predict_confidence
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
        securities = conn.execute(select(Security.symbol, Security.sector)).all()
    sectors = {row.symbol: row.sector for row in securities}

    # Chargé une seule fois pour tout l'univers : sert à la fois à détecter
    # chaque titre et à fournir le contexte de marché (`market_trend`) au
    # modèle appris de `engine.scoring`.
    price_frames = {symbol: load_prices(engine, symbol) for symbol in sectors}
    price_frames = {symbol: df for symbol, df in price_frames.items() if not df.empty}

    inserted = 0
    for symbol, df in price_frames.items():
        matches = detect_all(df)
        if not matches:
            continue
        with engine.begin() as conn:
            for match in matches:
                confidence = predict_confidence(match, df, sectors[symbol], price_frames)
                conn.execute(
                    PatternDetected.__table__.insert().values(
                        symbol=symbol,
                        pattern_type=match.pattern_type,
                        detected_at=match.detected_at,
                        confidence=confidence,
                        context=match.context,
                    )
                )
                inserted += 1
    return inserted


if __name__ == "__main__":
    count = run()
    print(f"{count} figures détectées et insérées dans patterns_detected.")
