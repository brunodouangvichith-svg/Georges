"""Détecteurs de figures de continuation : Bull Flag, Bear Flag,
Ascending Triangle, Descending Triangle, Falling Wedge, Rising Wedge.

Contrairement aux figures de retournement (`reversal.py`), ces détecteurs ne
travaillent que sur une fenêtre récente (``WINDOW`` barres) : ce sont des
figures de court terme qui se forment près du prix actuel.

Paramètres géométriques :

- ``WINDOW`` (30 barres) : fenêtre d'analyse pour les triangles/biseaux.
- ``FLAG_WINDOW`` (25 barres) et ``POLE_FRACTION`` (0.4) : pour les drapeaux,
  les premières ``POLE_FRACTION`` barres de la fenêtre sont le "mât"
  (mouvement impulsif), le reste est le "drapeau" (consolidation).
- ``MIN_POLE_RETURN`` (0.08 = 8 %) : variation minimale du mât pour être
  considéré comme un mouvement impulsif significatif.
- ``MAX_FLAG_RETRACE_RATIO`` (0.5) : l'amplitude du drapeau ne doit pas
  dépasser 50 % de l'amplitude du mât (sinon ce n'est plus une simple pause).
- ``MIN_TREND_SLOPE`` (0.001 = 0.1 %) : pente minimale (relative, par pas
  entre extrema) pour qu'une ligne de support/résistance soit considérée
  montante ou descendante plutôt que plate.
- ``MIN_CONVERGENCE`` (0.15 = 15 %) : rétrécissement minimal de l'écart entre
  les deux lignes de tendance (haute et basse), mesuré entre le premier et le
  dernier extremum de la figure, pour qu'un biseau (wedge) soit considéré
  convergent.
"""

import numpy as np
import pandas as pd

from engine.confidence import confidence_score, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.common import (
    BREAKOUT_BUFFER,
    LEVEL_TOLERANCE,
    MIN_PATTERN_BARS,
    PatternMatch,
    fit_trendline,
    local_maxima_idx,
    local_minima_idx,
    relative_diff,
    rsi,
    tail_window,
)


def _rsi_at_last(close) -> float | None:
    """Même helper que `reversal.py` — dupliqué plutôt que partagé pour
    éviter un import croisé entre modules de détection indépendants (aucun
    des deux ne dépend de l'autre aujourd'hui)."""
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)

WINDOW = 30
FLAG_WINDOW = 25
POLE_FRACTION = 0.4
MIN_POLE_RETURN = 0.08
MAX_FLAG_RETRACE_RATIO = 0.5
MIN_TREND_SLOPE = 0.001
MIN_CONVERGENCE = 0.15


def _flatness_quality(values, level):
    max_dev = max(relative_diff(v, level) for v in values)
    return float(np.clip(1.0 - max_dev / LEVEL_TOLERANCE, 0.0, 1.0)), max_dev


def _slope_quality(slope, reference=MIN_TREND_SLOPE):
    return float(np.clip(abs(slope) / (reference * 3), 0.0, 1.0))


def detect_ascending_triangle(df) -> list[PatternMatch]:
    w = tail_window(df, WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    maxima, minima = local_maxima_idx(close.values), local_minima_idx(close.values)
    if len(maxima) < 2 or len(minima) < 2:
        return []

    resistance_level = float(close.iloc[maxima].mean())
    flatness_quality, max_dev = _flatness_quality(close.iloc[maxima].values, resistance_level)
    if max_dev > LEVEL_TOLERANCE:
        return []

    support_slope, support_intercept = fit_trendline(minima, close.iloc[minima].values)
    normalized_slope = support_slope / resistance_level
    if normalized_slope < MIN_TREND_SLOPE:
        return []

    last_close = close.iloc[-1]
    if last_close <= resistance_level * (1 + BREAKOUT_BUFFER):
        return []

    geometry_quality = 0.5 * flatness_quality + 0.5 * _slope_quality(normalized_slope)
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=True)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=True)

    return [
        PatternMatch(
            pattern_type="Ascending Triangle",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "resistance": resistance_level,
                "support_slope": support_slope,
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]


def detect_descending_triangle(df) -> list[PatternMatch]:
    w = tail_window(df, WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    maxima, minima = local_maxima_idx(close.values), local_minima_idx(close.values)
    if len(maxima) < 2 or len(minima) < 2:
        return []

    support_level = float(close.iloc[minima].mean())
    flatness_quality, max_dev = _flatness_quality(close.iloc[minima].values, support_level)
    if max_dev > LEVEL_TOLERANCE:
        return []

    resistance_slope, _ = fit_trendline(maxima, close.iloc[maxima].values)
    normalized_slope = resistance_slope / support_level
    if normalized_slope > -MIN_TREND_SLOPE:
        return []

    last_close = close.iloc[-1]
    if last_close >= support_level * (1 - BREAKOUT_BUFFER):
        return []

    geometry_quality = 0.5 * flatness_quality + 0.5 * _slope_quality(normalized_slope)
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=False)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=False)

    return [
        PatternMatch(
            pattern_type="Descending Triangle",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "support": support_level,
                "resistance_slope": resistance_slope,
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]


def _wedge(df, bullish: bool) -> list[PatternMatch]:
    w = tail_window(df, WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    maxima, minima = local_maxima_idx(close.values), local_minima_idx(close.values)
    if len(maxima) < 2 or len(minima) < 2:
        return []

    level = float(close.mean())
    upper_slope, upper_intercept = fit_trendline(maxima, close.iloc[maxima].values)
    lower_slope, lower_intercept = fit_trendline(minima, close.iloc[minima].values)
    norm_upper, norm_lower = upper_slope / level, lower_slope / level

    expected_sign = 1 if not bullish else -1  # rising wedge (baissier) : pentes positives ; falling wedge (haussier) : pentes négatives
    if expected_sign * norm_upper < MIN_TREND_SLOPE or expected_sign * norm_lower < MIN_TREND_SLOPE:
        return []

    # Convergence : l'écart entre les deux lignes de tendance (évaluées aux
    # positions des extrema, pas sur toute la fenêtre) doit se resserrer entre
    # le début et la fin de la figure. On évite volontairement d'inclure la
    # dernière barre (la cassure) dans cette mesure : une fois la cassure
    # confirmée, le prix dépasse par construction le canal, ce qui élargirait
    # artificiellement l'écart "de fin" et masquerait la convergence réelle.
    x_start = int(min(maxima.min(), minima.min()))
    x_end = int(max(maxima.max(), minima.max()))
    gap_start = (upper_slope * x_start + upper_intercept) - (lower_slope * x_start + lower_intercept)
    gap_end = (upper_slope * x_end + upper_intercept) - (lower_slope * x_end + lower_intercept)
    if gap_start <= 0 or gap_end >= gap_start * (1 - MIN_CONVERGENCE):
        return []

    last_x = len(close) - 1
    last_close = close.iloc[-1]

    if bullish:
        upper_line_at_last = upper_slope * last_x + upper_intercept
        if last_close <= upper_line_at_last * (1 + BREAKOUT_BUFFER):
            return []
    else:
        lower_line_at_last = lower_slope * last_x + lower_intercept
        if last_close >= lower_line_at_last * (1 - BREAKOUT_BUFFER):
            return []

    convergence_ratio = 1.0 - gap_end / gap_start
    slope_quality = 0.5 * _slope_quality(norm_upper) + 0.5 * _slope_quality(norm_lower)
    geometry_quality = 0.5 * slope_quality + 0.5 * float(np.clip(convergence_ratio / (2 * MIN_CONVERGENCE), 0.0, 1.0))
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=bullish)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=bullish)

    return [
        PatternMatch(
            pattern_type="Falling Wedge" if bullish else "Rising Wedge",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "upper_slope": upper_slope,
                "lower_slope": lower_slope,
                "convergence_ratio": convergence_ratio,
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]


def detect_falling_wedge(df) -> list[PatternMatch]:
    return _wedge(df, bullish=True)


def detect_rising_wedge(df) -> list[PatternMatch]:
    return _wedge(df, bullish=False)


def _flag(df, bullish: bool) -> list[PatternMatch]:
    w = tail_window(df, FLAG_WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    pole_end = max(2, int(len(w) * POLE_FRACTION))
    # La dernière barre de la fenêtre est la candidate à la cassure : elle est
    # testée contre le canal du drapeau, mais ne doit pas participer à sa
    # construction (sinon un canal "en retard" absorbe la cassure elle-même).
    pole, flag = close.iloc[:pole_end], close.iloc[pole_end:-1]
    if len(flag) < 3:
        return []

    pole_return = (pole.iloc[-1] - pole.iloc[0]) / abs(pole.iloc[0])
    if bullish and pole_return < MIN_POLE_RETURN:
        return []
    if not bullish and pole_return > -MIN_POLE_RETURN:
        return []

    pole_amplitude = abs(pole.iloc[-1] - pole.iloc[0])
    flag_amplitude = flag.max() - flag.min()
    if flag_amplitude >= pole_amplitude * MAX_FLAG_RETRACE_RATIO:
        return []

    x_flag = np.arange(pole_end, pole_end + len(flag))
    flag_slope, flag_intercept = fit_trendline(x_flag, flag.values)
    normalized_flag_slope = flag_slope / close.mean()
    # Le drapeau doit être plat ou légèrement contraire au mât, jamais une
    # poursuite franche dans le même sens (ce serait alors une continuation
    # sans pause, pas un drapeau).
    if bullish and normalized_flag_slope > MIN_TREND_SLOPE:
        return []
    if not bullish and normalized_flag_slope < -MIN_TREND_SLOPE:
        return []

    last_x = len(close) - 1
    channel_half_width = flag_amplitude / 2
    flag_center_at_last = flag_slope * last_x + flag_intercept
    last_close = close.iloc[-1]

    if bullish:
        breakout_level = flag_center_at_last + channel_half_width
        if last_close <= breakout_level * (1 + BREAKOUT_BUFFER):
            return []
    else:
        breakout_level = flag_center_at_last - channel_half_width
        if last_close >= breakout_level * (1 - BREAKOUT_BUFFER):
            return []

    pole_quality = float(np.clip(abs(pole_return) / (2 * MIN_POLE_RETURN), 0.0, 1.0))
    tightness_quality = float(np.clip(1.0 - flag_amplitude / (pole_amplitude * MAX_FLAG_RETRACE_RATIO), 0.0, 1.0))
    geometry_quality = 0.5 * pole_quality + 0.5 * tightness_quality
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=bullish)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=bullish)

    return [
        PatternMatch(
            pattern_type="Bull Flag" if bullish else "Bear Flag",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "pole_return": pole_return,
                "pole_amplitude": float(pole_amplitude),
                "flag_amplitude": float(flag_amplitude),
                "flag_low": float(flag.min()),
                "flag_high": float(flag.max()),
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]


def detect_bull_flag(df) -> list[PatternMatch]:
    return _flag(df, bullish=True)


def detect_bear_flag(df) -> list[PatternMatch]:
    return _flag(df, bullish=False)
