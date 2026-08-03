"""Utilitaires géométriques partagés par tous les détecteurs de `engine/patterns/`.

Tous les détecteurs travaillent sur des règles géométriques appliquées aux
extrema locaux de la série de prix (`scipy.signal.argrelextrema`), sans deep
learning. Les tolérances ci-dessous sont volontairement centralisées ici
plutôt que dupliquées dans chaque fichier de pattern :

- ``EXTREMA_ORDER`` (3) : nombre de barres de part et d'autre qu'un point doit
  dominer (strictement) pour être retenu comme extremum local. Une valeur
  plus grande lisse le bruit mais rate les figures courtes ; 3 convient à des
  séries quotidiennes sur quelques semaines/mois.
- ``LEVEL_TOLERANCE`` (0.03 = 3 %) : écart relatif maximal entre deux niveaux
  de prix pour les considérer "au même niveau" (les deux creux d'un Double
  Bottom, les deux épaules d'un Head & Shoulders, une ligne d'encolure, etc.).
- ``MIN_PATTERN_BARS`` (10) : nombre minimal de barres couvertes par une
  figure pour être considérée significative (évite le bruit sur des fenêtres
  trop courtes).
- ``BREAKOUT_BUFFER`` (0.002 = 0.2 %) : marge exigée au-delà d'un niveau de
  résistance/support pour valider une cassure (breakout/breakdown), afin
  d'éviter de confirmer sur un simple bruit de clôture.

Toutes les fonctions de détection prennent un ``pandas.DataFrame`` indexé par
date, trié par ordre chronologique croissant, avec les colonnes
``open, high, low, close, volume``.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

EXTREMA_ORDER = 3
LEVEL_TOLERANCE = 0.03
MIN_PATTERN_BARS = 10
BREAKOUT_BUFFER = 0.002
RSI_WINDOW = 14
RSI_NEUTRAL_ZONE = 50.0


@dataclass
class PatternMatch:
    """Une détection, prête à être insérée dans `patterns_detected`."""

    pattern_type: str
    detected_at: pd.Timestamp
    confidence: float
    context: dict


def local_maxima_idx(values, order: int = EXTREMA_ORDER) -> np.ndarray:
    """Indices des maxima locaux stricts de `values`."""
    return argrelextrema(np.asarray(values, dtype=float), np.greater, order=order)[0]


def local_minima_idx(values, order: int = EXTREMA_ORDER) -> np.ndarray:
    """Indices des minima locaux stricts de `values`."""
    return argrelextrema(np.asarray(values, dtype=float), np.less, order=order)[0]


def relative_diff(a: float, b: float) -> float:
    """Écart relatif entre `a` et `b`, normalisé par leur échelle commune."""
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale


def within_tolerance(a: float, b: float, tolerance: float = LEVEL_TOLERANCE) -> bool:
    """Vrai si `a` et `b` sont à moins de `tolerance` (relatif) l'un de l'autre."""
    return relative_diff(a, b) <= tolerance


def closeness_score(a: float, b: float, tolerance: float = LEVEL_TOLERANCE) -> float:
    """1.0 si `a` == `b`, dégradant linéairement vers 0.0 à `tolerance` d'écart relatif."""
    return float(np.clip(1.0 - relative_diff(a, b) / tolerance, 0.0, 1.0))


def prominence_score(diff_ratio: float, min_prominence: float) -> float:
    """0.0 sous `min_prominence` d'écart relatif, montant linéairement à 1.0
    à 2x `min_prominence` (au-delà, l'écart supplémentaire n'ajoute rien)."""
    return float(np.clip(diff_ratio / (2 * min_prominence), 0.0, 1.0))


def relative_slope(y) -> float:
    """Pente d'une régression linéaire simple sur `y`, normalisée par le
    niveau moyen de la série (pente exprimée en fraction du prix par barre,
    comparable entre titres à des échelles de prix différentes)."""
    y = np.asarray(y, dtype=float)
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y))
    slope, _ = np.polyfit(x, y, 1)
    level = np.mean(np.abs(y)) or 1e-9
    return slope / level


def fit_trendline(x_idx, y_vals) -> tuple[float, float]:
    """Régression linéaire (pente, ordonnée à l'origine) passant par les
    points ``(x_idx, y_vals)`` — utilisée pour évaluer une ligne de tendance
    (résistance, support, bord de canal) à une position `x` quelconque via
    ``slope * x + intercept``."""
    slope, intercept = np.polyfit(np.asarray(x_idx, dtype=float), np.asarray(y_vals, dtype=float), 1)
    return float(slope), float(intercept)


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, window: int = RSI_WINDOW) -> pd.Series:
    """RSI de Wilder (1978) : ``100 - 100/(1+RS)``, RS = moyenne lissée des
    hausses / moyenne lissée des baisses sur `window` séances. Lissage de
    Wilder (``ewm(alpha=1/window, adjust=False)``), pas une simple moyenne
    mobile — c'est la formule exacte citée dans `George_AnalyseTechnique_
    Kabbaj_Synthese.md` §4. `NaN` tant que moins de `window` observations ne
    sont disponibles (comme `sma` ci-dessus) ; une moyenne de baisses nulle
    (hausse ininterrompue) donne un RS infini, donc un RSI de 100 — géré via
    `replace(0, np.nan)` puis une division par NaN, jamais une exception."""
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    # avg_loss nul (hausse ininterrompue sur la fenêtre) : RS infini -> RSI
    # doit être 100, pas NaN (`avg_gain.notna()` exclut les lignes de tête où
    # la fenêtre n'est pas encore remplie, où avg_loss vaut aussi NaN).
    zero_loss = avg_loss.eq(0) & avg_gain.notna()
    result = result.where(~zero_loss, 100.0)
    # Prix parfaitement plat (aucune hausse ni baisse) : neutre, pas 100.
    flat = avg_loss.eq(0) & avg_gain.eq(0)
    return result.where(~flat, 50.0)


def last_row(df: pd.DataFrame):
    return df.iloc[-1]


def tail_window(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Les `window` dernières lignes de `df` (ou `df` entier s'il est plus court)."""
    return df.iloc[-window:] if len(df) > window else df
