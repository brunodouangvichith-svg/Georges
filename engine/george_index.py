"""George Index par panier — implémentation. La formule exacte est
documentée dans `engine/george_index.md` ; toute modification ici doit y
être répercutée.

Module sans accès DB : il travaille sur des structures déjà chargées
(patterns actifs, prix), pour rester testable sur des données synthétiques
(voir tests/test_george_index.py). Le chargement depuis la base est fait
par `engine/compute_george_index.py` (script).
"""

import numpy as np
import pandas as pd

from engine.features import VOLUME_LOOKBACK, relative_volume

ACTIVE_WINDOW_SESSIONS = 5
MOMENTUM_WINDOW_SESSIONS = 20
MOMENTUM_SCALE = 20.0
MOMENTUM_CAP = 0.15
VOLUME_LOOKBACK_SESSIONS = VOLUME_LOOKBACK
VOLUME_SCALE = 1.0
VOLUME_CAP = 0.10


def _weighted_average(values_and_weights: list[tuple[float, float]]) -> float | None:
    total_weight = sum(w for _, w in values_and_weights)
    if total_weight == 0:
        return None
    return sum(v * w for v, w in values_and_weights) / total_weight


def most_recent_active_confidence(
    patterns: pd.DataFrame, symbol: str, as_of, active_window_sessions: int = ACTIVE_WINDOW_SESSIONS
) -> float | None:
    """Confiance de la figure la plus convaincante encore active pour
    `symbol` : parmi les lignes de `patterns` (colonnes `symbol`,
    `detected_at`, `confidence`) détectées dans les `active_window_sessions`
    précédant `as_of`, renvoie la confiance la plus élevée. `None` si
    aucune figure active."""
    cutoff = as_of - pd.Timedelta(days=active_window_sessions * 1.5)  # marge pour week-ends/jours fériés
    active = patterns[
        (patterns["symbol"] == symbol) & (patterns["detected_at"] > cutoff) & (patterns["detected_at"] <= as_of)
    ]
    if active.empty:
        return None
    return float(active["confidence"].max())


def momentum_pct(df: pd.DataFrame, window: int = MOMENTUM_WINDOW_SESSIONS) -> float | None:
    """Rendement (%) entre la clôture la plus récente et celle d'il y a
    `window` séances. `None` si l'historique est insuffisant."""
    if len(df) <= window:
        return None
    base = df["close"].iloc[-1 - window]
    if base == 0:
        return None
    return float((df["close"].iloc[-1] - base) / base * 100)


def compute_george_index(
    basket_symbols: list[tuple[str, float]],
    patterns: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    as_of,
) -> float | None:
    """`basket_symbols` : liste de `(symbol, weight)` du panier (voir
    `basket_securities`). `patterns` : DataFrame `patterns_detected`
    (colonnes `symbol`, `detected_at`, `confidence`) de tout l'univers —
    pas seulement ce panier, le filtrage se fait ici. `price_frames` :
    historique OHLCV par symbole. `as_of` : date de référence (typiquement
    aujourd'hui). Renvoie `None` si aucun titre du panier n'a de figure
    active (voir `engine/george_index.md`)."""
    confidences = []
    momentums = []
    rel_volumes = []

    for symbol, weight in basket_symbols:
        confidence = most_recent_active_confidence(patterns, symbol, as_of)
        if confidence is not None:
            confidences.append((confidence, weight))

        df = price_frames.get(symbol)
        if df is None or df.empty:
            continue
        m = momentum_pct(df)
        if m is not None:
            momentums.append((m, weight))
        rv = relative_volume(df, len(df) - 1, lookback=VOLUME_LOOKBACK_SESSIONS)
        if rv is not None:
            rel_volumes.append((rv, weight))

    base_score = _weighted_average(confidences)
    if base_score is None:
        return None

    basket_momentum = _weighted_average(momentums) or 0.0
    momentum_multiplier = 1 + float(np.clip(basket_momentum / MOMENTUM_SCALE, -MOMENTUM_CAP, MOMENTUM_CAP))

    basket_rel_volume = _weighted_average(rel_volumes)
    basket_rel_volume = basket_rel_volume if basket_rel_volume is not None else 1.0
    volume_multiplier = 1 + float(np.clip((basket_rel_volume - 1) / VOLUME_SCALE, -VOLUME_CAP, VOLUME_CAP))

    index = base_score * momentum_multiplier * volume_multiplier
    return round(float(np.clip(index, 0.0, 100.0)), 1)
