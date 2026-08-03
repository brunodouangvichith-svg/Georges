"""Détecteurs de figures en bougies japonaises — ajoutés après lecture de
*Maîtriser l'analyse technique avec Thami Kabbaj* (voir
`George_AnalyseTechnique_Kabbaj_Synthese.md` §2.1), absentes des 13
détecteurs chartistes (`reversal.py`/`continuation.py`/`breakout.py`), qui ne
travaillent que sur des formations multi-bougies au niveau du prix.

Différence architecturale majeure avec les 13 détecteurs existants : ceux-ci
scannent tout ou partie de l'historique (extrema locaux) ; une figure en
bougie ne porte que sur les 1 à 3 **dernières** bougies — pas de scan
historique nécessaire.

Règle du livre appliquée strictement (§2.1/§6 de la synthèse) : *« aucune
figure de bougie seule n'est un signal exploitable »*. Chaque détecteur exige
donc, en plus de la géométrie OHLC, que la **tendance récente** (les
`TREND_CONTEXT_BARS` séances précédant la bougie de signal, hors bougie(s) de
signal elle(s)-même(s)) aille dans le sens attendu par la figure — sinon `[]`,
même si la géométrie seule serait valide. C'est un filtre dur (avant même de
calculer une confiance), distinct des facteurs `trend_conf`/`rsi_conf` de
`engine/confidence.py` qui, eux, continuent de pondérer la confiance finale
exactement comme pour les 13 détecteurs existants (même architecture, mêmes
poids GEOMETRY/VOLUME/TREND/RSI).

Chaque paire de figures (marteau/pendu, marteau inversé/étoile filante) a la
**même géométrie**, seule la tendance précédente et le sens qui en découle
diffèrent — reflet direct de la façon dont le livre les présente. Avalement/
étoile/nuage-pénétrante ont leur sens déterminé par la couleur des bougies
elles-mêmes (haussière/baissière), la tendance précédente ne fait que
confirmer que le contexte est propice à un retournement.
"""

import numpy as np
import pandas as pd

from engine.confidence import confidence_score, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.common import PatternMatch, relative_slope, rsi

TREND_CONTEXT_BARS = 10
MIN_TREND_SLOPE_FOR_CANDLESTICK = 0.001  # même ordre de grandeur que continuation.py:MIN_TREND_SLOPE

DOJI_MAX_BODY_RATIO = 0.1  # corps <= 10% du range (open≈close)
SMALL_BODY_MAX_RATIO = 0.35  # "petit corps" pour marteau/étoile filante, relatif au range
LONG_SHADOW_MIN_RATIO = 2.0  # grande ombre >= 2x le corps
SHORT_SHADOW_MAX_RATIO = 1.0  # ombre courte <= 1x le corps
MIN_PIERCING_PENETRATION = 0.5  # pénétration minimale dans le corps précédent (nuage noir / pénétrante)


def _rsi_at_last(close) -> float | None:
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)


def _candle_metrics(row) -> dict:
    body = abs(row["close"] - row["open"])
    upper_shadow = row["high"] - max(row["open"], row["close"])
    lower_shadow = min(row["open"], row["close"]) - row["low"]
    candle_range = row["high"] - row["low"]
    return {
        "body": float(body),
        "upper_shadow": float(upper_shadow),
        "lower_shadow": float(lower_shadow),
        "range": float(candle_range),
        "bullish": bool(row["close"] > row["open"]),
        "bearish": bool(row["close"] < row["open"]),
    }


def _preceding_trend(df, signal_bars: int = 1) -> str:
    """"up" / "down" / "flat" selon la pente des clôtures sur `TREND_CONTEXT_BARS`
    séances précédant la ou les `signal_bars` dernière(s) bougie(s) de la
    figure (jamais la bougie de signal elle-même, qui pourrait déjà amorcer
    le retournement et fausserait la mesure de la tendance qu'elle est censée
    retourner)."""
    end = len(df) - signal_bars
    start = max(0, end - TREND_CONTEXT_BARS)
    window = df["close"].iloc[start:end]
    if len(window) < TREND_CONTEXT_BARS // 2:
        return "flat"
    slope = relative_slope(window.values)
    if slope > MIN_TREND_SLOPE_FOR_CANDLESTICK:
        return "up"
    if slope < -MIN_TREND_SLOPE_FOR_CANDLESTICK:
        return "down"
    return "flat"


def _score_and_match(df, pattern_type, geometry_quality, bullish, signal_idx, extra_context) -> list[PatternMatch]:
    close = df["close"]
    at_idx = len(close) - 1
    volume_conf = volume_confirmation(df["volume"], at_idx)
    trend_conf = trend_alignment(close, bullish=bullish)
    rsi_conf = rsi_confirmation(close, at_idx, bullish=bullish)
    return [
        PatternMatch(
            pattern_type=pattern_type,
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={"signal_index": signal_idx, "rsi_14": _rsi_at_last(close), **extra_context},
        )
    ]


# --- Doji ---------------------------------------------------------------


def _doji_shape(df) -> dict | None:
    if len(df) < TREND_CONTEXT_BARS + 1:
        return None
    m = _candle_metrics(df.iloc[-1])
    if m["range"] == 0 or m["body"] / m["range"] > DOJI_MAX_BODY_RATIO:
        return None
    return m


def detect_bullish_doji(df) -> list[PatternMatch]:
    """Doji après une baisse : indécision au creux, retournement haussier
    possible (nécessite confirmation par tendance/RSI, jamais seul — §2.1
    de la synthèse)."""
    m = _doji_shape(df)
    if m is None or _preceding_trend(df) != "down":
        return []
    geometry_quality = float(np.clip(1.0 - m["body"] / (m["range"] * DOJI_MAX_BODY_RATIO), 0.0, 1.0))
    return _score_and_match(df, "Bullish Doji", geometry_quality, True, len(df) - 1, {})


def detect_bearish_doji(df) -> list[PatternMatch]:
    """Doji après une hausse : indécision au sommet, retournement baissier
    possible."""
    m = _doji_shape(df)
    if m is None or _preceding_trend(df) != "up":
        return []
    geometry_quality = float(np.clip(1.0 - m["body"] / (m["range"] * DOJI_MAX_BODY_RATIO), 0.0, 1.0))
    return _score_and_match(df, "Bearish Doji", geometry_quality, False, len(df) - 1, {})


# --- Marteau / Pendu (même géométrie, contexte opposé) -------------------


def _hammer_shape(df) -> dict | None:
    if len(df) < TREND_CONTEXT_BARS + 1:
        return None
    m = _candle_metrics(df.iloc[-1])
    if m["range"] == 0 or m["body"] == 0:
        return None
    if m["body"] / m["range"] > SMALL_BODY_MAX_RATIO:
        return None
    if m["lower_shadow"] < m["body"] * LONG_SHADOW_MIN_RATIO:
        return None
    if m["upper_shadow"] > m["body"] * SHORT_SHADOW_MAX_RATIO:
        return None
    return m


def detect_hammer(df) -> list[PatternMatch]:
    """Petit corps en haut du range, grande ombre basse (épuisement des
    vendeurs) — retournement haussier après une baisse."""
    m = _hammer_shape(df)
    if m is None or _preceding_trend(df) != "down":
        return []
    geometry_quality = float(np.clip(m["lower_shadow"] / (m["body"] * LONG_SHADOW_MIN_RATIO * 1.5), 0.0, 1.0))
    return _score_and_match(df, "Hammer", geometry_quality, True, len(df) - 1, {})


def detect_hanging_man(df) -> list[PatternMatch]:
    """Même géométrie que le marteau, mais après une hausse : retournement
    baissier (épuisement des acheteurs)."""
    m = _hammer_shape(df)
    if m is None or _preceding_trend(df) != "up":
        return []
    geometry_quality = float(np.clip(m["lower_shadow"] / (m["body"] * LONG_SHADOW_MIN_RATIO * 1.5), 0.0, 1.0))
    return _score_and_match(df, "Hanging Man", geometry_quality, False, len(df) - 1, {})


# --- Marteau inversé / Étoile filante (même géométrie, contexte opposé) --


def _inverted_hammer_shape(df) -> dict | None:
    if len(df) < TREND_CONTEXT_BARS + 1:
        return None
    m = _candle_metrics(df.iloc[-1])
    if m["range"] == 0 or m["body"] == 0:
        return None
    if m["body"] / m["range"] > SMALL_BODY_MAX_RATIO:
        return None
    if m["upper_shadow"] < m["body"] * LONG_SHADOW_MIN_RATIO:
        return None
    if m["lower_shadow"] > m["body"] * SHORT_SHADOW_MAX_RATIO:
        return None
    return m


def detect_inverted_hammer(df) -> list[PatternMatch]:
    """Petit corps en bas du range, grande ombre haute — retournement
    haussier après une baisse."""
    m = _inverted_hammer_shape(df)
    if m is None or _preceding_trend(df) != "down":
        return []
    geometry_quality = float(np.clip(m["upper_shadow"] / (m["body"] * LONG_SHADOW_MIN_RATIO * 1.5), 0.0, 1.0))
    return _score_and_match(df, "Inverted Hammer", geometry_quality, True, len(df) - 1, {})


def detect_shooting_star(df) -> list[PatternMatch]:
    """Même géométrie que le marteau inversé, mais après une hausse :
    retournement baissier."""
    m = _inverted_hammer_shape(df)
    if m is None or _preceding_trend(df) != "up":
        return []
    geometry_quality = float(np.clip(m["upper_shadow"] / (m["body"] * LONG_SHADOW_MIN_RATIO * 1.5), 0.0, 1.0))
    return _score_and_match(df, "Shooting Star", geometry_quality, False, len(df) - 1, {})


# --- Avalement haussier / baissier ---------------------------------------


def detect_bullish_engulfing(df) -> list[PatternMatch]:
    """Bougie baissière suivie d'une bougie haussière dont le corps avale
    entièrement le corps précédent — retournement haussier fort, surtout
    sur un creux de marché."""
    if len(df) < TREND_CONTEXT_BARS + 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if not prev_m["bearish"] or not curr_m["bullish"]:
        return []
    if not (curr["open"] <= prev["close"] and curr["close"] >= prev["open"]):
        return []
    if _preceding_trend(df, signal_bars=2) != "down":
        return []
    engulf_ratio = curr_m["body"] / max(prev_m["body"], 1e-9)
    geometry_quality = float(np.clip(engulf_ratio / 2.0, 0.0, 1.0))
    return _score_and_match(df, "Bullish Engulfing", geometry_quality, True, len(df) - 1, {})


def detect_bearish_engulfing(df) -> list[PatternMatch]:
    """Symétrique de l'avalement haussier — retournement baissier fort sur
    un sommet."""
    if len(df) < TREND_CONTEXT_BARS + 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if not prev_m["bullish"] or not curr_m["bearish"]:
        return []
    if not (curr["open"] >= prev["close"] and curr["close"] <= prev["open"]):
        return []
    if _preceding_trend(df, signal_bars=2) != "up":
        return []
    engulf_ratio = curr_m["body"] / max(prev_m["body"], 1e-9)
    geometry_quality = float(np.clip(engulf_ratio / 2.0, 0.0, 1.0))
    return _score_and_match(df, "Bearish Engulfing", geometry_quality, False, len(df) - 1, {})


# --- Étoile du matin / du soir (3 bougies) -------------------------------


def detect_morning_star(df) -> list[PatternMatch]:
    """3 bougies : grand corps noir, petit corps (gap en dessous), grand
    corps blanc qui avale souvent 2-3 bougies précédentes — retournement
    haussier après une baisse marquée."""
    if len(df) < TREND_CONTEXT_BARS + 3:
        return []
    first, middle, last = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    first_m, middle_m, last_m = _candle_metrics(first), _candle_metrics(middle), _candle_metrics(last)
    if not first_m["bearish"] or not last_m["bullish"]:
        return []
    if middle_m["range"] == 0 or middle_m["body"] / middle_m["range"] > SMALL_BODY_MAX_RATIO:
        return []
    if max(middle["open"], middle["close"]) >= first["close"]:
        return []  # pas de gap baissier entre la 1re et la 2e bougie
    midpoint_first = (first["open"] + first["close"]) / 2
    if last["close"] <= midpoint_first:
        return []  # la 3e bougie doit reprendre au moins la moitié du 1er corps
    if _preceding_trend(df, signal_bars=3) != "down":
        return []
    penetration = (last["close"] - midpoint_first) / max(abs(first["close"] - first["open"]), 1e-9)
    geometry_quality = float(np.clip(penetration, 0.0, 1.0))
    return _score_and_match(df, "Morning Star", geometry_quality, True, len(df) - 1, {})


def detect_evening_star(df) -> list[PatternMatch]:
    """Symétrique de l'étoile du matin — retournement baissier après une
    tendance haussière puissante."""
    if len(df) < TREND_CONTEXT_BARS + 3:
        return []
    first, middle, last = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    first_m, middle_m, last_m = _candle_metrics(first), _candle_metrics(middle), _candle_metrics(last)
    if not first_m["bullish"] or not last_m["bearish"]:
        return []
    if middle_m["range"] == 0 or middle_m["body"] / middle_m["range"] > SMALL_BODY_MAX_RATIO:
        return []
    if min(middle["open"], middle["close"]) <= first["close"]:
        return []  # pas de gap haussier entre la 1re et la 2e bougie
    midpoint_first = (first["open"] + first["close"]) / 2
    if last["close"] >= midpoint_first:
        return []
    if _preceding_trend(df, signal_bars=3) != "up":
        return []
    penetration = (midpoint_first - last["close"]) / max(abs(first["close"] - first["open"]), 1e-9)
    geometry_quality = float(np.clip(penetration, 0.0, 1.0))
    return _score_and_match(df, "Evening Star", geometry_quality, False, len(df) - 1, {})


# --- Nuage noir / Pénétrante ----------------------------------------------


def detect_dark_cloud_cover(df) -> list[PatternMatch]:
    """Bougie blanche suivie d'une noire qui ouvre au-dessus du corps blanc
    mais clôture au moins à mi-corps à l'intérieur (sans l'avaler
    entièrement, sinon c'est un avalement baissier) — retournement baissier,
    signal légèrement moins fort que l'avalement."""
    if len(df) < TREND_CONTEXT_BARS + 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if not prev_m["bullish"] or not curr_m["bearish"]:
        return []
    if curr["open"] <= prev["close"]:
        return []  # pas d'ouverture en gap haussier au-dessus du corps blanc
    midpoint_prev = (prev["open"] + prev["close"]) / 2
    penetration = (prev["close"] - curr["close"]) / max(abs(prev["close"] - prev["open"]), 1e-9)
    if curr["close"] >= midpoint_prev or curr["close"] <= prev["open"]:
        return []  # doit clôturer entre le point médian et l'ouverture du corps blanc (pas un avalement complet)
    if _preceding_trend(df, signal_bars=2) != "up":
        return []
    geometry_quality = float(np.clip(penetration, 0.0, 1.0))
    return _score_and_match(df, "Dark Cloud Cover", geometry_quality, False, len(df) - 1, {})


def detect_piercing_line(df) -> list[PatternMatch]:
    """Symétrique du nuage noir en contexte baissier — retournement haussier
    après une tendance baissière."""
    if len(df) < TREND_CONTEXT_BARS + 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if not prev_m["bearish"] or not curr_m["bullish"]:
        return []
    if curr["open"] >= prev["close"]:
        return []  # pas d'ouverture en gap baissier sous le corps noir
    midpoint_prev = (prev["open"] + prev["close"]) / 2
    penetration = (curr["close"] - prev["close"]) / max(abs(prev["close"] - prev["open"]), 1e-9)
    if curr["close"] <= midpoint_prev or curr["close"] >= prev["open"]:
        return []
    if _preceding_trend(df, signal_bars=2) != "down":
        return []
    geometry_quality = float(np.clip(penetration, 0.0, 1.0))
    return _score_and_match(df, "Piercing Line", geometry_quality, True, len(df) - 1, {})
