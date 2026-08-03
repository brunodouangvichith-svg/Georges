"""Assemble le jeu d'entraînement du modèle de confiance à partir de la base
(`patterns_detected` + `price_history_long` (via `engine.run_detection.load_prices`)
+ `securities`) et l'écrit sur disque pour le notebook d'entraînement offline
(Phase 2).

Usage :
    python -m engine.build_training_set
"""

import os

import pandas as pd
from sqlalchemy import select

from engine.backtest import TRAINING_HORIZON, build_sample, build_training_set, compute_market_trend
from engine.run_detection import load_prices
from ingestion.db import get_engine
from ingestion.models import PatternDetected, Security

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "training_set.parquet")


def run(output_path: str = OUTPUT_PATH) -> pd.DataFrame:
    engine = get_engine()

    with engine.begin() as conn:
        pattern_rows = conn.execute(
            select(
                PatternDetected.symbol,
                PatternDetected.pattern_type,
                PatternDetected.detected_at,
                Security.sector,
            ).join(Security, Security.symbol == PatternDetected.symbol)
        ).all()

    symbols = {row.symbol for row in pattern_rows}
    price_frames = {symbol: load_prices(engine, symbol) for symbol in symbols}
    price_frames = {symbol: df for symbol, df in price_frames.items() if not df.empty}

    samples = []
    for row in pattern_rows:
        df = price_frames.get(row.symbol)
        if df is None:
            continue
        at_idx = int(df.index.get_indexer([row.detected_at], method="nearest")[0])
        if at_idx < 0:
            continue
        market_trend = compute_market_trend(price_frames, row.detected_at)
        samples.append(build_sample(df, at_idx, row.pattern_type, row.sector, market_trend))

    dataset = build_training_set(samples)
    if dataset.empty:
        # Ne pas écrire un fichier vide (sans même les colonnes attendues) :
        # le notebook d'entraînement ne teste que l'existence du fichier
        # pour décider d'utiliser les données réelles plutôt que la
        # génération synthétique, et planterait sur un DataFrame vide. Un
        # pattern ne devient backtestable qu'une fois `TRAINING_HORIZON`
        # séances passées depuis sa détection (voir `engine/backtest.py`) —
        # juste après une première détection, ce cas est normal.
        return dataset
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dataset.to_parquet(output_path, index=False)
    return dataset


if __name__ == "__main__":
    ds = run()
    if ds.empty:
        print(
            "0 exemple backtestable pour l'instant (aucun pattern détecté n'a encore "
            f"{TRAINING_HORIZON} séances de recul) — {OUTPUT_PATH} non écrit."
        )
    else:
        print(f"{len(ds)} exemples écrits dans {OUTPUT_PATH}")
