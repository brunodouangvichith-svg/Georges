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

from engine.patterns.common import (
    BOLLINGER_WINDOW,
    RSI_WINDOW,
    STOCHASTIC_WINDOW,
    bollinger_bands,
    macd,
    rsi,
    sma,
    stochastic_oscillator,
)

VOLUME_LOOKBACK = 20
ATR_WINDOW = 14
SMA_SHORT = 50
SMA_LONG = 200

# Colonnes de features partagées entre l'entraînement
# (engine/notebooks/train_confidence_model.ipynb) et l'inférence
# (engine/scoring.py) — toute figure/titre produisant ces colonnes peut être
# scoré par le modèle appris. `rsi_14`, puis `macd_hist_pct`/`bb_percent_b`/
# `stochastic_k` ajoutées après lecture de
# George_AnalyseTechnique_Kabbaj_Synthese.md — voir `rsi_at` ci-dessous pour
# pourquoi elles ne sont volontairement pas des features "gatantes" comme les
# autres (`build_feature_row` dans `engine/scoring.py`) : elles nécessitent
# nettement moins d'historique que la SMA200 déjà gatante.
CATEGORICAL_FEATURE_COLUMNS = ["pattern_type", "sector"]
NUMERIC_FEATURE_COLUMNS = [
    "relative_volume",
    "atr_pct",
    "market_trend",
    "price_over_sma50",
    "price_over_sma200",
    "sma50_over_sma200",
    "rsi_14",
    "macd_hist_pct",
    "bb_percent_b",
    "stochastic_k",
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


def rsi_at(df: pd.DataFrame, at_idx: int, window: int = RSI_WINDOW) -> float | None:
    """RSI (14) à `at_idx`. Ne nécessite que `window` séances d'historique —
    nettement moins que la SMA200 déjà gatante de `position_vs_moving_averages`
    — donc volontairement traitée comme `market_trend` dans
    `engine/scoring.py:build_feature_row` (imputée si absente), pas comme
    `atr_pct`/`relative_volume`/les moyennes mobiles ci-dessus (qui bloquent
    le scoring appris s'ils manquent)."""
    value = rsi(df["close"], window=window).iloc[at_idx]
    return None if pd.isna(value) else float(value)


def macd_hist_pct(df: pd.DataFrame, at_idx: int) -> float | None:
    """Histogramme MACD (ligne MACD - ligne de signal) à `at_idx`, exprimé en
    % du prix de clôture — même normalisation que `atr_pct`, pour rester
    comparable entre titres à des échelles de prix différentes. Traitée comme
    `rsi_14` ci-dessus (non gatante) dans `engine/scoring.py:build_feature_row`."""
    _, _, histogram = macd(df["close"])
    value = histogram.iloc[at_idx]
    close = df["close"].iloc[at_idx]
    if pd.isna(value) or close == 0:
        return None
    return float(value / close)


def bb_percent_b(df: pd.DataFrame, at_idx: int, window: int = BOLLINGER_WINDOW) -> float | None:
    """Position du prix dans les bandes de Bollinger à `at_idx` (« %b ») :
    0.0 sur la bande basse, 1.0 sur la bande haute, 0.5 sur la médiane — peut
    sortir de [0, 1] lors d'une cassure des bandes elles-mêmes. `None` si la
    fenêtre `window` n'est pas encore pleine ou si les bandes sont plates
    (aucune volatilité, division par zéro). Traitée comme `rsi_14` ci-dessus
    (non gatante) dans `engine/scoring.py:build_feature_row`."""
    _, upper, lower = bollinger_bands(df["close"], window=window)
    up, low = upper.iloc[at_idx], lower.iloc[at_idx]
    if pd.isna(up) or pd.isna(low) or up == low:
        return None
    return float((df["close"].iloc[at_idx] - low) / (up - low))


def stochastic_k_at(df: pd.DataFrame, at_idx: int, window: int = STOCHASTIC_WINDOW) -> float | None:
    """%K de l'oscillateur stochastique à `at_idx` (0-100). Traitée comme
    `rsi_14` ci-dessus (non gatante) dans `engine/scoring.py:build_feature_row`."""
    percent_k, _ = stochastic_oscillator(df["high"], df["low"], df["close"], window=window)
    value = percent_k.iloc[at_idx]
    return None if pd.isna(value) else float(value)
