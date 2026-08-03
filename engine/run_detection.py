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
from ingestion.models import PatternDetected, PriceHistoryLong, Security


def load_prices(engine, symbol: str) -> pd.DataFrame:
    """Charge l'historique de prix d'un titre depuis `price_history_long`
    (jusqu'à 10 ans, `ingestion/price_history.py`) plutôt que `prices_ohlcv`
    (2 ans, `ingestion/ohlcv.py`) — demandé directement par l'utilisateur pour
    que la détection de figures et tout ce qui en découle (propositions,
    George Index, PnL du portefeuille, rapports) disposent d'un historique
    bien plus profond. `prices_ohlcv` n'est plus lu par aucun consommateur
    depuis ce changement (voir CLAUDE.md) — son ingestion quotidienne a été
    retirée du workflow en conséquence, mais la table elle-même n'a pas été
    supprimée."""
    stmt = (
        select(
            PriceHistoryLong.ts,
            PriceHistoryLong.open,
            PriceHistoryLong.high,
            PriceHistoryLong.low,
            PriceHistoryLong.close,
            PriceHistoryLong.volume,
        )
        .where(PriceHistoryLong.symbol == symbol)
        .order_by(PriceHistoryLong.ts)
    )
    df = pd.read_sql(stmt, engine, index_col="ts")
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": "int64"})
    # Une séance encore en cours au moment de l'ingestion peut avoir un
    # `close` NaN (open/high/low/volume réels par ailleurs — même piège déjà
    # rencontré dans `api/routers/portfolios.py:_current_price_and_pnl`).
    # Filtrée ici, à la source, plutôt que dans chaque consommateur
    # individuellement (détecteurs de figures, `engine/confidence.py`,
    # `engine/scoring.py`/`engine/features.py`) : un vrai bug découvert lors
    # du premier déploiement, où une dernière bougie NaN a produit une
    # confiance NaN (`patterns_detected`), puis un `entry_price` NaN
    # (`decisions`), jusqu'à faire planter `engine.propose_decisions` sur
    # une comparaison Postgres avec un `Decimal('NaN')`.
    return df[df["close"].notna()]


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
                confidence, confidence_source = predict_confidence(match, df, sectors[symbol], price_frames)
                conn.execute(
                    PatternDetected.__table__.insert().values(
                        symbol=symbol,
                        pattern_type=match.pattern_type,
                        detected_at=match.detected_at,
                        confidence=confidence,
                        # `confidence_source` documente si `confidence`
                        # ci-dessus vient du modèle appris ou de la formule
                        # heuristique (`engine.confidence.confidence_score`)
                        # — les sous-scores stockés par le détecteur
                        # (`geometry_quality` etc.) ne redonnent le score
                        # final par leur somme pondérée QUE dans ce second
                        # cas ; voir `agents/context.py`/`explainer_system.txt`.
                        context={**match.context, "confidence_source": confidence_source},
                    )
                )
                inserted += 1
    return inserted


if __name__ == "__main__":
    count = run()
    print(f"{count} figures détectées et insérées dans patterns_detected.")
