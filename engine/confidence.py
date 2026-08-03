"""Score de confiance heuristique (0-100) pour une figure détectée.

Combine quatre composantes, chacune normalisée sur [0, 1] :

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
- **confirmation RSI** (`rsi_confirmation`) : ajoutée après lecture de
  *Maîtriser l'analyse technique avec Thami Kabbaj* (voir
  `George_AnalyseTechnique_Kabbaj_Synthese.md` §3.2) — l'auteur y documente un
  cas réel (CAC 40, avril 1997) où une tête-épaules cassée a avorté
  précisément parce que le RSI n'a jamais cassé sa propre zone de neutralité,
  citant explicitement *« les indicateurs techniques priment parfois sur les
  figures graphiques »*. Applique le même filtre uniformément aux 13
  détecteurs déjà existants (pas seulement aux figures de retournement),
  cohérent avec le fait que volume/tendance s'appliquent déjà à tous.

Pondération : ``GEOMETRY_WEIGHT`` (0.4) + ``VOLUME_WEIGHT`` (0.2) +
``TREND_WEIGHT`` (0.2) + ``RSI_WEIGHT`` (0.2) = 1.0. Rebalancée par rapport
aux poids précédents (0.5/0.25/0.25) pour faire de la place au RSI tout en
gardant la géométrie comme facteur dominant.
"""

import numpy as np
import pandas as pd

from engine.patterns.common import RSI_NEUTRAL_ZONE, rsi, sma

GEOMETRY_WEIGHT = 0.4
VOLUME_WEIGHT = 0.2
TREND_WEIGHT = 0.2
RSI_WEIGHT = 0.2

VOLUME_LOOKBACK = 20
SMA_SHORT = 50
SMA_LONG = 200


def volume_confirmation(volume: pd.Series, at_idx: int, lookback: int = VOLUME_LOOKBACK) -> float:
    """Ratio volume(at_idx) / moyenne(volume des `lookback` séances précédentes),
    saturé sur [0, 1] : un ratio de 0.5x ou moins vaut 0, un ratio de 2x ou
    plus vaut 1, la relation est linéaire entre les deux.

    Repli neutre (0.5) si le volume du jour visé est manquant (`NaN`) — un
    vrai cas rencontré en réingérant en pleine séance (marché encore ouvert,
    même bug de bar incomplète que `close` ailleurs dans le projet, voir
    `api/routers/portfolios.py:_current_price_and_pnl`), qui produisait
    silencieusement une confiance `NaN` en base sans ce garde-fou (attrapé
    en essayant d'insérer une décision dessus : `decimal.InvalidOperation`
    sur une comparaison `<` avec un `Decimal('NaN')`)."""
    if pd.isna(volume.iloc[at_idx]):
        return 0.5
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


def rsi_confirmation(close: pd.Series, at_idx: int, bullish: bool) -> float:
    """1.0 si le RSI est du bon côté de sa zone de neutralité (`RSI_NEUTRAL_ZONE`,
    50) pour le sens de la figure (au-dessus pour une figure haussière,
    en dessous pour une figure baissière), 0.0 sinon, 0.5 si l'historique est
    insuffisant (`RSI_WINDOW` séances) ou si la valeur est `NaN`."""
    rsi_series = rsi(close)
    if at_idx >= len(rsi_series):
        return 0.5
    value = rsi_series.iloc[at_idx]
    if pd.isna(value):
        return 0.5
    above_neutral = value > RSI_NEUTRAL_ZONE
    return 1.0 if above_neutral == bullish else 0.0


def confidence_score(geometry_quality: float, volume_conf: float, trend_conf: float, rsi_conf: float) -> float:
    """Combine les quatre composantes en un score final 0-100 (1 décimale)."""
    raw = (
        GEOMETRY_WEIGHT * geometry_quality
        + VOLUME_WEIGHT * volume_conf
        + TREND_WEIGHT * trend_conf
        + RSI_WEIGHT * rsi_conf
    )
    return round(float(np.clip(raw, 0.0, 1.0)) * 100, 1)
