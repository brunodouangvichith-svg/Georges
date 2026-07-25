"""Score de confiance heuristique (0-100) pour une figure détectée.

Combine trois composantes, chacune normalisée sur [0, 1] :

- **netteté géométrique** (``geometry_quality``) : calculée par chaque
  détecteur (`engine/patterns/*.py`), spécifique à la forme de la figure
  (proximité des niveaux, prominence des extrema, pente des lignes de
  tendance...).
- **confirmation de volume** (`volume_confirmation`) : ratio entre le volume
  du jour clé de la figure (cassure, second creux, etc.) et le volume moyen
  des ``VOLUME_LOOKBACK`` séances précédentes.
- **alignement de tendance** (`trend_alignment`) : position du prix par
  rapport aux moyennes mobiles ``SMA_SHORT``/``SMA_LONG`` (50/200 séances) —
  une figure haussière est plus crédible si la tendance de fond est déjà
  haussière, et inversement pour une figure baissière.

Pondération : ``GEOMETRY_WEIGHT`` (0.5) + ``VOLUME_WEIGHT`` (0.25) +
``TREND_WEIGHT`` (0.25) = 1.0.
"""

import numpy as np
import pandas as pd

from engine.patterns.common import sma

GEOMETRY_WEIGHT = 0.5
VOLUME_WEIGHT = 0.25
TREND_WEIGHT = 0.25

VOLUME_LOOKBACK = 20
SMA_SHORT = 50
SMA_LONG = 200


def volume_confirmation(volume: pd.Series, at_idx: int, lookback: int = VOLUME_LOOKBACK) -> float:
    """Ratio volume(at_idx) / moyenne(volume des `lookback` séances précédentes),
    saturé sur [0, 1] : un ratio de 0.5x ou moins vaut 0, un ratio de 2x ou
    plus vaut 1, la relation est linéaire entre les deux."""
    start = max(0, at_idx - lookback)
    baseline = volume.iloc[start:at_idx]
    if len(baseline) == 0 or baseline.mean() == 0:
        return 0.5
    ratio = volume.iloc[at_idx] / baseline.mean()
    return float(np.clip((ratio - 0.5) / 1.5, 0.0, 1.0))


def trend_alignment(close: pd.Series, bullish: bool) -> float:
    """1.0 si la tendance de fond (SMA50 vs SMA200, prix vs SMA50) soutient
    le sens du pattern, 0.0 si elle s'y oppose totalement, 0.5 si
    l'historique est trop court pour juger."""
    if len(close) < SMA_LONG:
        return 0.5
    sma50 = sma(close, SMA_SHORT).iloc[-1]
    sma200 = sma(close, SMA_LONG).iloc[-1]
    price = close.iloc[-1]
    if pd.isna(sma50) or pd.isna(sma200):
        return 0.5

    above_50 = price > sma50
    trend_up = sma50 > sma200
    score = 0.0
    score += 0.5 if (above_50 == bullish) else 0.0
    score += 0.5 if (trend_up == bullish) else 0.0
    return score


def confidence_score(geometry_quality: float, volume_conf: float, trend_conf: float) -> float:
    """Combine les trois composantes en un score final 0-100 (1 décimale)."""
    raw = (
        GEOMETRY_WEIGHT * geometry_quality
        + VOLUME_WEIGHT * volume_conf
        + TREND_WEIGHT * trend_conf
    )
    return round(float(np.clip(raw, 0.0, 1.0)) * 100, 1)
