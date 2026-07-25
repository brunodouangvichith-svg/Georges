"""Détecteurs de figures de retournement : Double Bottom, Double Top,
Head & Shoulders (et inverse), Cup & Handle.

Paramètres géométriques spécifiques à ce fichier (au-delà des tolérances
communes de `common.py`) :

- ``MIN_PEAK_PROMINENCE`` (0.05 = 5 %) : écart minimal, relatif au niveau des
  deux creux/sommets encadrants, que doit avoir le sommet/creux intermédiaire
  (le pic entre les deux creux d'un Double Bottom, la tête d'un Head &
  Shoulders...) pour être considéré significatif plutôt que du bruit.
- ``MIN_CUP_DEPTH`` (0.08 = 8 %) : profondeur minimale du Cup & Handle
  (écart entre le rebord et le point bas de la coupe), relative au rebord.
- ``MAX_HANDLE_DEPTH_RATIO`` (0.5) : profondeur maximale de l'anse (handle)
  relativement à la profondeur de la coupe — une anse trop profonde invalide
  la figure (ce serait alors un nouveau creux, pas une consolidation).

Toutes les figures ne sont retenues qu'une fois **confirmées** par une
cassure du niveau clé (au-dessus pour les figures haussières, au-dessous
pour les baissières) sur la dernière clôture disponible — voir
`BREAKOUT_BUFFER` dans `common.py`. Chaque détecteur ne renvoie que la
formation la plus récente (celle dont la cassure coïncide avec la dernière
clôture), pas tout l'historique des appariements possibles.
"""

import numpy as np

from engine.confidence import confidence_score, trend_alignment, volume_confirmation
from engine.patterns.common import (
    BREAKOUT_BUFFER,
    MIN_PATTERN_BARS,
    PatternMatch,
    closeness_score,
    local_maxima_idx,
    local_minima_idx,
    prominence_score,
    relative_diff,
    within_tolerance,
)

MIN_PEAK_PROMINENCE = 0.05
MIN_CUP_DEPTH = 0.08
MAX_HANDLE_DEPTH_RATIO = 0.5


def detect_double_bottom(df) -> list[PatternMatch]:
    close = df["close"]
    minima = local_minima_idx(close.values)
    maxima = local_maxima_idx(close.values)

    for i in range(len(minima) - 2, -1, -1):
        b1, b2 = int(minima[i]), int(minima[i + 1])
        if b2 - b1 < MIN_PATTERN_BARS:
            continue
        p1, p2 = close.iloc[b1], close.iloc[b2]
        if not within_tolerance(p1, p2):
            continue

        between = maxima[(maxima > b1) & (maxima < b2)]
        if len(between) == 0:
            continue
        peak_idx = int(between[np.argmax(close.iloc[between].values)])
        peak = close.iloc[peak_idx]
        prominence = relative_diff(peak, max(p1, p2))
        if peak <= max(p1, p2) or prominence < MIN_PEAK_PROMINENCE:
            continue

        last_close = close.iloc[-1]
        if last_close <= peak * (1 + BREAKOUT_BUFFER):
            continue

        geometry_quality = 0.5 * closeness_score(p1, p2) + 0.5 * prominence_score(prominence, MIN_PEAK_PROMINENCE)
        volume_conf = volume_confirmation(df["volume"], len(close) - 1)
        trend_conf = trend_alignment(close, bullish=True)

        return [
            PatternMatch(
                pattern_type="Double Bottom",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf),
                context={
                    "bottom_1": {"index": b1, "price": float(p1)},
                    "bottom_2": {"index": b2, "price": float(p2)},
                    "resistance": {"index": peak_idx, "price": float(peak)},
                },
            )
        ]
    return []


def detect_double_top(df) -> list[PatternMatch]:
    close = df["close"]
    maxima = local_maxima_idx(close.values)
    minima = local_minima_idx(close.values)

    for i in range(len(maxima) - 2, -1, -1):
        t1, t2 = int(maxima[i]), int(maxima[i + 1])
        if t2 - t1 < MIN_PATTERN_BARS:
            continue
        p1, p2 = close.iloc[t1], close.iloc[t2]
        if not within_tolerance(p1, p2):
            continue

        between = minima[(minima > t1) & (minima < t2)]
        if len(between) == 0:
            continue
        trough_idx = int(between[np.argmin(close.iloc[between].values)])
        trough = close.iloc[trough_idx]
        prominence = relative_diff(trough, min(p1, p2))
        if trough >= min(p1, p2) or prominence < MIN_PEAK_PROMINENCE:
            continue

        last_close = close.iloc[-1]
        if last_close >= trough * (1 - BREAKOUT_BUFFER):
            continue

        geometry_quality = 0.5 * closeness_score(p1, p2) + 0.5 * prominence_score(prominence, MIN_PEAK_PROMINENCE)
        volume_conf = volume_confirmation(df["volume"], len(close) - 1)
        trend_conf = trend_alignment(close, bullish=False)

        return [
            PatternMatch(
                pattern_type="Double Top",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf),
                context={
                    "top_1": {"index": t1, "price": float(p1)},
                    "top_2": {"index": t2, "price": float(p2)},
                    "support": {"index": trough_idx, "price": float(trough)},
                },
            )
        ]
    return []


def detect_head_and_shoulders(df) -> list[PatternMatch]:
    close = df["close"]
    maxima = local_maxima_idx(close.values)
    minima = local_minima_idx(close.values)

    for i in range(len(maxima) - 3, -1, -1):
        ls, head, rs = int(maxima[i]), int(maxima[i + 1]), int(maxima[i + 2])
        if rs - ls < MIN_PATTERN_BARS:
            continue
        p_ls, p_head, p_rs = close.iloc[ls], close.iloc[head], close.iloc[rs]
        if not within_tolerance(p_ls, p_rs):
            continue
        if p_head <= max(p_ls, p_rs):
            continue

        left_troughs = minima[(minima > ls) & (minima < head)]
        right_troughs = minima[(minima > head) & (minima < rs)]
        if len(left_troughs) == 0 or len(right_troughs) == 0:
            continue
        n1 = int(left_troughs[np.argmin(close.iloc[left_troughs].values)])
        n2 = int(right_troughs[np.argmin(close.iloc[right_troughs].values)])
        neckline_1, neckline_2 = close.iloc[n1], close.iloc[n2]
        if not within_tolerance(neckline_1, neckline_2):
            continue
        neckline = (neckline_1 + neckline_2) / 2

        last_close = close.iloc[-1]
        if last_close >= neckline * (1 - BREAKOUT_BUFFER):
            continue

        head_prominence = relative_diff(p_head, max(p_ls, p_rs))
        geometry_quality = (
            0.4 * closeness_score(p_ls, p_rs)
            + 0.3 * closeness_score(neckline_1, neckline_2)
            + 0.3 * prominence_score(head_prominence, MIN_PEAK_PROMINENCE)
        )
        volume_conf = volume_confirmation(df["volume"], len(close) - 1)
        trend_conf = trend_alignment(close, bullish=False)

        return [
            PatternMatch(
                pattern_type="Head & Shoulders",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf),
                context={
                    "left_shoulder": {"index": ls, "price": float(p_ls)},
                    "head": {"index": head, "price": float(p_head)},
                    "right_shoulder": {"index": rs, "price": float(p_rs)},
                    "neckline": {"points": [n1, n2], "price": float(neckline)},
                },
            )
        ]
    return []


def detect_inverse_head_and_shoulders(df) -> list[PatternMatch]:
    close = df["close"]
    minima = local_minima_idx(close.values)
    maxima = local_maxima_idx(close.values)

    for i in range(len(minima) - 3, -1, -1):
        ls, head, rs = int(minima[i]), int(minima[i + 1]), int(minima[i + 2])
        if rs - ls < MIN_PATTERN_BARS:
            continue
        p_ls, p_head, p_rs = close.iloc[ls], close.iloc[head], close.iloc[rs]
        if not within_tolerance(p_ls, p_rs):
            continue
        if p_head >= min(p_ls, p_rs):
            continue

        left_peaks = maxima[(maxima > ls) & (maxima < head)]
        right_peaks = maxima[(maxima > head) & (maxima < rs)]
        if len(left_peaks) == 0 or len(right_peaks) == 0:
            continue
        n1 = int(left_peaks[np.argmax(close.iloc[left_peaks].values)])
        n2 = int(right_peaks[np.argmax(close.iloc[right_peaks].values)])
        neckline_1, neckline_2 = close.iloc[n1], close.iloc[n2]
        if not within_tolerance(neckline_1, neckline_2):
            continue
        neckline = (neckline_1 + neckline_2) / 2

        last_close = close.iloc[-1]
        if last_close <= neckline * (1 + BREAKOUT_BUFFER):
            continue

        head_prominence = relative_diff(p_head, min(p_ls, p_rs))
        geometry_quality = (
            0.4 * closeness_score(p_ls, p_rs)
            + 0.3 * closeness_score(neckline_1, neckline_2)
            + 0.3 * prominence_score(head_prominence, MIN_PEAK_PROMINENCE)
        )
        volume_conf = volume_confirmation(df["volume"], len(close) - 1)
        trend_conf = trend_alignment(close, bullish=True)

        return [
            PatternMatch(
                pattern_type="Inverse Head & Shoulders",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf),
                context={
                    "left_shoulder": {"index": ls, "price": float(p_ls)},
                    "head": {"index": head, "price": float(p_head)},
                    "right_shoulder": {"index": rs, "price": float(p_rs)},
                    "neckline": {"points": [n1, n2], "price": float(neckline)},
                },
            )
        ]
    return []


def detect_cup_and_handle(df) -> list[PatternMatch]:
    close = df["close"]
    n = len(close)
    if n < MIN_PATTERN_BARS * 2:
        return []

    minima = local_minima_idx(close.values)
    if len(minima) == 0:
        return []

    # Le fond de la coupe : le minimum local le plus prononcé, à l'exclusion
    # d'une petite marge au tout début/fin de série (il faut un rebord des
    # deux côtés).
    margin = max(MIN_PATTERN_BARS // 2, 1)
    candidates = minima[(minima > margin) & (minima < n - margin)]
    if len(candidates) == 0:
        return []
    cup_bottom_idx = int(candidates[np.argmin(close.iloc[candidates].values)])
    cup_bottom = close.iloc[cup_bottom_idx]

    left_rim_idx = int(close.iloc[:cup_bottom_idx].values.argmax())
    left_rim = close.iloc[left_rim_idx]

    # Rebord droit : le premier sommet local après le fond (la reprise qui
    # complète la coupe). Ne pas prendre le maximum global du reste de la
    # série : une fois la cassure de l'anse confirmée, le prix dépasse
    # justement ce rebord, ce qui désignerait à tort le point de cassure
    # lui-même comme "rebord".
    maxima = local_maxima_idx(close.values)
    after_maxima = maxima[maxima > cup_bottom_idx]
    if len(after_maxima) == 0:
        return []
    right_rim_idx = int(after_maxima[0])
    right_rim = close.iloc[right_rim_idx]

    if not within_tolerance(left_rim, right_rim):
        return []
    cup_depth = relative_diff(cup_bottom, max(left_rim, right_rim))
    if cup_depth < MIN_CUP_DEPTH:
        return []
    if right_rim_idx - cup_bottom_idx < MIN_PATTERN_BARS // 2:
        return []

    # Anse : après le rebord droit, un repli plus faible que la coupe.
    handle = close.iloc[right_rim_idx + 1 :]
    if len(handle) < 3:
        return []
    handle_low = handle.min()
    handle_depth = relative_diff(handle_low, right_rim)
    if handle_depth >= cup_depth * MAX_HANDLE_DEPTH_RATIO:
        return []

    last_close = close.iloc[-1]
    breakout_level = max(left_rim, right_rim)
    if last_close <= breakout_level * (1 + BREAKOUT_BUFFER):
        return []

    geometry_quality = (
        0.4 * closeness_score(left_rim, right_rim)
        + 0.3 * prominence_score(cup_depth, MIN_CUP_DEPTH)
        + 0.3 * (1.0 - np.clip(handle_depth / (cup_depth * MAX_HANDLE_DEPTH_RATIO), 0.0, 1.0))
    )
    volume_conf = volume_confirmation(df["volume"], n - 1)
    trend_conf = trend_alignment(close, bullish=True)

    return [
        PatternMatch(
            pattern_type="Cup & Handle",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf),
            context={
                "left_rim": {"index": left_rim_idx, "price": float(left_rim)},
                "cup_bottom": {"index": cup_bottom_idx, "price": float(cup_bottom)},
                "right_rim": {"index": right_rim_idx, "price": float(right_rim)},
                "handle_low": float(handle_low),
            },
        )
    ]
