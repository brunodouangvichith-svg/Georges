"""Features utilisées pour l'apprentissage du score de confiance (Phase 2)
et pour l'inférence en production (`engine/scoring.py`).

Toutes les fonctions prennent un DataFrame OHLCV (colonnes ``open, high,
low, close, volume``, index de dates croissantes) et une position entière
``at_idx`` (généralement le dernier indice disponible au moment de la
détection). Elles renvoient ``None`` quand la feature n'est pas calculable
(historique insuffisant) plutôt qu'une valeur arbitraire — c'est ce signal
que `engine/scoring.py` utilise pour décider de retomber sur l'heuristique
de la Phase 1.

Paramètres :
- ``VOLUME_LOOKBACK`` (20 séances) : fenêtre de référence pour le volume relatif.
- ``ATR_WINDOW`` (14 séances) : fenêtre standard de l'Average True Range.
- ``SMA_SHORT`` / ``SMA_LONG`` (50 / 200 séances) : moyennes mobiles de contexte.
"""

import pandas as pd

from engine.patterns.common import sma

VOLUME_LOOKBACK = 20
ATR_WINDOW = 14
SMA_SHORT = 50
SMA_LONG = 200

# Colonnes de features partagées entre l'entraînement
# (engine/notebooks/train_confidence_model.ipynb) et l'inférence
# (engine/scoring.py) — toute figure/titre produisant ces colonnes peut être
# scoré par le modèle appris.
CATEGORICAL_FEATURE_COLUMNS = ["pattern_type", "sector"]
NUMERIC_FEATURE_COLUMNS = [
    "relative_volume",
    "atr_pct",
    "market_trend",
    "price_over_sma50",
    "price_over_sma200",
    "sma50_over_sma200",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURE_COLUMNS + NUMERIC_FEATURE_COLUMNS


def relative_volume(df: pd.DataFrame, at_idx: int, lookback: int = VOLUME_LOOKBACK) -> float | None:
    """Ratio volume(at_idx) / moyenne des `lookback` séances précédentes."""
    start = max(0, at_idx - lookback)
    baseline = df["volume"].iloc[start:at_idx]
    if len(baseline) == 0 or baseline.mean() == 0:
        return None
    return float(df["volume"].iloc[at_idx] / baseline.mean())


def average_true_range(df: pd.DataFrame, window: int = ATR_WINDOW) -> pd.Series:
    """Average True Range — moyenne mobile simple du True Range (pas le
    lissage de Wilder, approximation suffisante pour une feature)."""
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def atr_pct(df: pd.DataFrame, at_idx: int, window: int = ATR_WINDOW) -> float | None:
    """ATR à `at_idx`, exprimé en % du prix de clôture (comparable entre titres)."""
    value = average_true_range(df, window=window).iloc[at_idx]
    close = df["close"].iloc[at_idx]
    if pd.isna(value) or close == 0:
        return None
    return float(value / close)


def position_vs_moving_averages(df: pd.DataFrame, at_idx: int) -> dict | None:
    """Position du prix par rapport aux moyennes mobiles 50/200 à `at_idx`.
    `None` si l'historique est insuffisant pour calculer la SMA200."""
    if at_idx < SMA_LONG - 1:
        return None
    close = df["close"]
    sma50 = sma(close, SMA_SHORT).iloc[at_idx]
    sma200 = sma(close, SMA_LONG).iloc[at_idx]
    if pd.isna(sma50) or pd.isna(sma200):
        return None
    price = close.iloc[at_idx]
    return {
        "price_over_sma50": float(price / sma50),
        "price_over_sma200": float(price / sma200),
        "sma50_over_sma200": float(sma50 / sma200),
    }
