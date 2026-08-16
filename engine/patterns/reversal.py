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

Ajouté ensuite (même fichier, mêmes conventions) — Triple Top/Bottom,
Rounding Top/Bottom, Diamond Top/Bottom :

- ``ROUNDING_WINDOW`` (``MIN_PATTERN_BARS * 3`` = 30) : fenêtre glissante sur
  laquelle une parabole (régression quadratique) est ajustée pour Rounding
  Top/Bottom, et sur laquelle la volatilité (range haut-bas par barre) est
  mesurée pour Diamond Top/Bottom (même taille de fenêtre, réutilisée telle
  quelle — pas de raison géométrique de les différencier).
- ``ROUNDING_MIN_R2`` (0.5) : qualité minimale de l'ajustement quadratique
  (R²) pour qu'une courbe soit retenue comme un vrai arrondi plutôt qu'un
  bruit ajusté approximativement par une parabole.
- ``ROUNDING_VERTEX_MARGIN`` (0.2 = 20 %) : le sommet de la parabole doit
  tomber dans les 60 % centraux de la fenêtre (ni dans les 20 % de tête, ni
  dans les 20 % de queue) pour écarter un simple coin ou une droite quasi
  plate plutôt qu'une vraie courbe.
- ``MIN_DIAMOND_SLOPE`` (0.001, même ordre de grandeur que
  `continuation.py:MIN_TREND_SLOPE`) : pente minimale (relative) exigée pour
  qu'une moitié de fenêtre soit considérée en expansion (1re moitié) ou en
  contraction (2e moitié) de volatilité plutôt que plate.
- ``DIAMOND_TREND_CONTEXT_BARS`` (``MIN_PATTERN_BARS``) : nombre de barres,
  immédiatement avant la fenêtre du diamant, utilisées pour vérifier le sens
  de la tendance qui précède (même principe que
  `candlestick.py:TREND_CONTEXT_BARS`, dupliqué ici plutôt qu'importé — voir
  la convention déjà en place dans ce fichier pour `_rsi_at_last`).
"""

import numpy as np
import pandas as pd

from engine.confidence import confidence_score, macd_confirmation, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.common import (
    BREAKOUT_BUFFER,
    MIN_PATTERN_BARS,
    PatternMatch,
    closeness_score,
    local_maxima_idx,
    local_minima_idx,
    macd,
    prominence_score,
    relative_diff,
    relative_slope,
    rsi,
    tail_window,
    within_tolerance,
)


def _rsi_at_last(close) -> float | None:
    """Valeur RSI (14) à la dernière séance, `None` si `NaN` (historique
    insuffisant) — stockée dans `context` pour que l'explication LLM
    (`agents/context.py`) puisse la citer sans recalcul."""
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)


def _macd_line_at_last(close) -> float | None:
    """Valeur de la ligne MACD (EMA12-EMA26) à la dernière séance, même rôle
    que `_rsi_at_last` mais pour le MACD — voir
    `engine/confidence.py:macd_confirmation`."""
    macd_line, _, _ = macd(close)
    value = macd_line.iloc[-1]
    return None if pd.isna(value) else float(value)

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
        rsi_conf = rsi_confirmation(close, len(close) - 1, bullish=True)
        macd_conf = macd_confirmation(close, len(close) - 1, bullish=True)

        return [
            PatternMatch(
                pattern_type="Double Bottom",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
                context={
                    "bottom_1": {"index": b1, "price": float(p1)},
                    "bottom_2": {"index": b2, "price": float(p2)},
                    "resistance": {"index": peak_idx, "price": float(peak)},
                    "rsi_14": _rsi_at_last(close),
                    "macd_line": _macd_line_at_last(close),
                    "geometry_quality": round(float(geometry_quality), 3),
                    "volume_confirmation": round(float(volume_conf), 3),
                    "trend_alignment": round(float(trend_conf), 3),
                    "rsi_confirmation": round(float(rsi_conf), 3),
                    "macd_confirmation": round(float(macd_conf), 3),
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
        rsi_conf = rsi_confirmation(close, len(close) - 1, bullish=False)
        macd_conf = macd_confirmation(close, len(close) - 1, bullish=False)

        return [
            PatternMatch(
                pattern_type="Double Top",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
                context={
                    "top_1": {"index": t1, "price": float(p1)},
                    "top_2": {"index": t2, "price": float(p2)},
                    "support": {"index": trough_idx, "price": float(trough)},
                    "rsi_14": _rsi_at_last(close),
                    "macd_line": _macd_line_at_last(close),
                    "geometry_quality": round(float(geometry_quality), 3),
                    "volume_confirmation": round(float(volume_conf), 3),
                    "trend_alignment": round(float(trend_conf), 3),
                    "rsi_confirmation": round(float(rsi_conf), 3),
                    "macd_confirmation": round(float(macd_conf), 3),
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
        rsi_conf = rsi_confirmation(close, len(close) - 1, bullish=False)
        macd_conf = macd_confirmation(close, len(close) - 1, bullish=False)

        return [
            PatternMatch(
                pattern_type="Head & Shoulders",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
                context={
                    "left_shoulder": {"index": ls, "price": float(p_ls)},
                    "head": {"index": head, "price": float(p_head)},
                    "right_shoulder": {"index": rs, "price": float(p_rs)},
                    "neckline": {"points": [n1, n2], "price": float(neckline)},
                    "rsi_14": _rsi_at_last(close),
                    "macd_line": _macd_line_at_last(close),
                    "geometry_quality": round(float(geometry_quality), 3),
                    "volume_confirmation": round(float(volume_conf), 3),
                    "trend_alignment": round(float(trend_conf), 3),
                    "rsi_confirmation": round(float(rsi_conf), 3),
                    "macd_confirmation": round(float(macd_conf), 3),
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
        rsi_conf = rsi_confirmation(close, len(close) - 1, bullish=True)
        macd_conf = macd_confirmation(close, len(close) - 1, bullish=True)

        return [
            PatternMatch(
                pattern_type="Inverse Head & Shoulders",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
                context={
                    "left_shoulder": {"index": ls, "price": float(p_ls)},
                    "head": {"index": head, "price": float(p_head)},
                    "right_shoulder": {"index": rs, "price": float(p_rs)},
                    "neckline": {"points": [n1, n2], "price": float(neckline)},
                    "rsi_14": _rsi_at_last(close),
                    "macd_line": _macd_line_at_last(close),
                    "geometry_quality": round(float(geometry_quality), 3),
                    "volume_confirmation": round(float(volume_conf), 3),
                    "trend_alignment": round(float(trend_conf), 3),
                    "rsi_confirmation": round(float(rsi_conf), 3),
                    "macd_confirmation": round(float(macd_conf), 3),
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
    rsi_conf = rsi_confirmation(close, n - 1, bullish=True)
    macd_conf = macd_confirmation(close, n - 1, bullish=True)

    return [
        PatternMatch(
            pattern_type="Cup & Handle",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
            context={
                "left_rim": {"index": left_rim_idx, "price": float(left_rim)},
                "cup_bottom": {"index": cup_bottom_idx, "price": float(cup_bottom)},
                "right_rim": {"index": right_rim_idx, "price": float(right_rim)},
                "handle_low": float(handle_low),
                "rsi_14": _rsi_at_last(close),
                "macd_line": _macd_line_at_last(close),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
                "macd_confirmation": round(float(macd_conf), 3),
            },
        )
    ]


# --- Triple Top / Triple Bottom ------------------------------------------
#
# Extension directe des Double Top/Bottom ci-dessus : au lieu de 2 sommets
# (creux) au même niveau encadrant un seul creux (sommet) intermédiaire, on
# exige 3 sommets (creux) consécutifs au même niveau, encadrant 2 creux
# (sommets) intermédiaires. Chaque creux (sommet) intermédiaire est validé
# pairwise contre les 2 sommets (creux) qui l'encadrent directement — même
# règle de prominence que Double Top/Bottom (`relative_diff` contre le
# extrême le plus défavorable des deux voisins), simplement appliquée deux
# fois plutôt qu'une.


def _triple_extreme(df, bullish: bool) -> list[PatternMatch]:
    """Triple Bottom (haussier) si `bullish`, Triple Top (baissier) sinon.

    Géométrie : 3 minima (Triple Bottom) ou 3 maxima (Triple Top) locaux
    consécutifs `e1 < e2 < e3`, tous au même niveau (`within_tolerance`
    deux-à-deux). Entre chaque paire consécutive d'extrema, l'extremum
    opposé le plus prononcé (le plus haut sommet pour un Triple Bottom, le
    plus bas creux pour un Triple Top) doit dépasser le niveau de référence
    (le plus haut des 2 creux encadrants pour un Triple Bottom, le plus bas
    des 2 sommets encadrants pour un Triple Top — même convention que
    `detect_double_bottom`/`detect_double_top` ci-dessus) d'au moins
    `MIN_PEAK_PROMINENCE`. La ligne de résistance (Triple Bottom) / support
    (Triple Top) retenue pour la confirmation est le plus haut des 2 sommets
    intermédiaires / le plus bas des 2 creux intermédiaires (énoncé de la
    figure). Confirmée par la cassure de cette ligne sur la dernière
    clôture, avec la même marge `BREAKOUT_BUFFER` que les figures à 2
    points."""
    close = df["close"]
    if bullish:
        extrema = local_minima_idx(close.values)
        opposite = local_maxima_idx(close.values)
    else:
        extrema = local_maxima_idx(close.values)
        opposite = local_minima_idx(close.values)

    for i in range(len(extrema) - 3, -1, -1):
        e1, e2, e3 = int(extrema[i]), int(extrema[i + 1]), int(extrema[i + 2])
        if e3 - e1 < MIN_PATTERN_BARS:
            continue
        p1, p2, p3 = close.iloc[e1], close.iloc[e2], close.iloc[e3]
        if not (within_tolerance(p1, p2) and within_tolerance(p2, p3) and within_tolerance(p1, p3)):
            continue

        between_1 = opposite[(opposite > e1) & (opposite < e2)]
        between_2 = opposite[(opposite > e2) & (opposite < e3)]
        if len(between_1) == 0 or len(between_2) == 0:
            continue

        if bullish:
            m1 = int(between_1[np.argmax(close.iloc[between_1].values)])
            m2 = int(between_2[np.argmax(close.iloc[between_2].values)])
        else:
            m1 = int(between_1[np.argmin(close.iloc[between_1].values)])
            m2 = int(between_2[np.argmin(close.iloc[between_2].values)])
        mid_1, mid_2 = close.iloc[m1], close.iloc[m2]

        # Référence pairwise, même convention que Double Bottom/Top : le
        # sommet intermédiaire doit dépasser le plus haut des 2 creux
        # voisins (Triple Bottom) ; le creux intermédiaire doit être sous le
        # plus bas des 2 sommets voisins (Triple Top).
        ref_1 = max(p1, p2) if bullish else min(p1, p2)
        ref_2 = max(p2, p3) if bullish else min(p2, p3)
        if bullish:
            invalid = mid_1 <= ref_1 or mid_2 <= ref_2
        else:
            invalid = mid_1 >= ref_1 or mid_2 >= ref_2
        prominence_1 = relative_diff(mid_1, ref_1)
        prominence_2 = relative_diff(mid_2, ref_2)
        if invalid or min(prominence_1, prominence_2) < MIN_PEAK_PROMINENCE:
            continue

        level = max(mid_1, mid_2) if bullish else min(mid_1, mid_2)
        level_idx = m1 if mid_1 == level else m2

        last_close = close.iloc[-1]
        if bullish and last_close <= level * (1 + BREAKOUT_BUFFER):
            continue
        if not bullish and last_close >= level * (1 - BREAKOUT_BUFFER):
            continue

        closeness = (closeness_score(p1, p2) + closeness_score(p2, p3) + closeness_score(p1, p3)) / 3
        prominence_quality = (
            prominence_score(prominence_1, MIN_PEAK_PROMINENCE) + prominence_score(prominence_2, MIN_PEAK_PROMINENCE)
        ) / 2
        geometry_quality = 0.5 * closeness + 0.5 * prominence_quality
        volume_conf = volume_confirmation(df["volume"], len(close) - 1)
        trend_conf = trend_alignment(close, bullish=bullish)
        rsi_conf = rsi_confirmation(close, len(close) - 1, bullish=bullish)
        macd_conf = macd_confirmation(close, len(close) - 1, bullish=bullish)

        extreme_key = "bottom" if bullish else "top"
        level_key = "resistance" if bullish else "support"

        return [
            PatternMatch(
                pattern_type="Triple Bottom" if bullish else "Triple Top",
                detected_at=df.index[-1],
                confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
                context={
                    f"{extreme_key}_1": {"index": e1, "price": float(p1)},
                    f"{extreme_key}_2": {"index": e2, "price": float(p2)},
                    f"{extreme_key}_3": {"index": e3, "price": float(p3)},
                    level_key: {"index": level_idx, "price": float(level)},
                    "rsi_14": _rsi_at_last(close),
                    "macd_line": _macd_line_at_last(close),
                    "geometry_quality": round(float(geometry_quality), 3),
                    "volume_confirmation": round(float(volume_conf), 3),
                    "trend_alignment": round(float(trend_conf), 3),
                    "rsi_confirmation": round(float(rsi_conf), 3),
                    "macd_confirmation": round(float(macd_conf), 3),
                },
            )
        ]
    return []


def detect_triple_bottom(df) -> list[PatternMatch]:
    return _triple_extreme(df, bullish=True)


def detect_triple_top(df) -> list[PatternMatch]:
    return _triple_extreme(df, bullish=False)


# --- Rounding Top / Rounding Bottom ---------------------------------------
#
# Contrairement aux figures ci-dessus (extrema locaux discrets), le Rounding
# Top/Bottom est une courbe lisse : on ajuste une parabole (régression
# quadratique) sur toute la fenêtre plutôt que de chercher des points
# pivots. Un vrai "arrondi" a son sommet quelque part au milieu de la
# fenêtre (ni un coin en tout début, ni en toute fin) et une variance bien
# expliquée par cette parabole (R² élevé) — sinon ce n'est qu'une droite ou
# du bruit sur lequel une parabole s'ajuste mal.

ROUNDING_WINDOW = MIN_PATTERN_BARS * 3
ROUNDING_MIN_R2 = 0.5
ROUNDING_VERTEX_MARGIN = 0.2  # sommet exigé dans les 60 % centraux de la fenêtre


def _rounding(df, bullish: bool) -> list[PatternMatch]:
    """Rounding Bottom (haussier, parabole tournée vers le haut, a > 0) si
    `bullish`, Rounding Top (baissier, a < 0) sinon.

    Ajuste ``close = a*x^2 + b*x + c`` (``np.polyfit`` degré 2) sur les
    `ROUNDING_WINDOW` dernières barres. Le sommet de la parabole
    (``x = -b/(2a)``) doit tomber dans les 60 % centraux de la fenêtre
    (`ROUNDING_VERTEX_MARGIN` de marge de chaque côté) — une vraie courbe,
    pas un coin près d'un bord. Le R² de l'ajustement doit être au moins
    `ROUNDING_MIN_R2`. Confirmée par une cassure de la dernière clôture
    au-delà du "rebord" (la clôture au tout début de la fenêtre) — le prix
    est reparti suffisamment loin de son point de départ pour valider la
    sortie de la figure, même marge `BREAKOUT_BUFFER` que les autres
    figures."""
    w = tail_window(df, ROUNDING_WINDOW)
    if len(w) < MIN_PATTERN_BARS * 2:
        return []
    close = w["close"]
    n = len(close)
    x = np.arange(n, dtype=float)
    y = close.values.astype(float)
    a, b, c = np.polyfit(x, y, 2)
    if bullish and a <= 0:
        return []
    if not bullish and a >= 0:
        return []

    vertex = -b / (2 * a)
    low_bound, high_bound = ROUNDING_VERTEX_MARGIN * n, (1 - ROUNDING_VERTEX_MARGIN) * n
    if not (low_bound <= vertex <= high_bound):
        return []

    fitted = a * x**2 + b * x + c
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if r_squared < ROUNDING_MIN_R2:
        return []

    rim = float(close.iloc[0])
    last_close = close.iloc[-1]
    if bullish and last_close <= rim * (1 + BREAKOUT_BUFFER):
        return []
    if not bullish and last_close >= rim * (1 - BREAKOUT_BUFFER):
        return []

    center = n / 2
    half_range = (1 - 2 * ROUNDING_VERTEX_MARGIN) * n / 2
    centering_quality = float(np.clip(1.0 - abs(vertex - center) / half_range, 0.0, 1.0))
    geometry_quality = 0.5 * float(np.clip(r_squared, 0.0, 1.0)) + 0.5 * centering_quality
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=bullish)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=bullish)
    macd_conf = macd_confirmation(df["close"], len(df) - 1, bullish=bullish)

    vertex_idx = int(round(vertex))
    vertex_price = float(a * vertex**2 + b * vertex + c)

    return [
        PatternMatch(
            pattern_type="Rounding Bottom" if bullish else "Rounding Top",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
            context={
                "rim": rim,
                "vertex": {"index": vertex_idx, "price": vertex_price},
                "r_squared": round(float(r_squared), 3),
                "rsi_14": _rsi_at_last(df["close"]),
                "macd_line": _macd_line_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
                "macd_confirmation": round(float(macd_conf), 3),
            },
        )
    ]


def detect_rounding_bottom(df) -> list[PatternMatch]:
    return _rounding(df, bullish=True)


def detect_rounding_top(df) -> list[PatternMatch]:
    return _rounding(df, bullish=False)


# --- Diamond Top / Diamond Bottom -----------------------------------------
#
# Volatilité (range haut-bas par barre) qui se dilate puis se contracte sur
# la fenêtre — silhouette en losange sur un graphique de prix. Contrairement
# à Rounding ci-dessus (courbe sur les *clôtures*), la géométrie ici porte
# sur l'*amplitude* de chaque barre, pas sur son niveau. La dernière barre de
# la fenêtre est la candidate à la cassure : comme `continuation.py:_flag`/
# `_wedge`, elle est délibérément exclue de la construction du "motif"
# (moitié 1/moitié 2) pour ne pas se tester elle-même contre un niveau
# qu'elle aurait servi à définir.

DIAMOND_WINDOW = ROUNDING_WINDOW  # même taille de fenêtre que Rounding ci-dessus
MIN_DIAMOND_SLOPE = 0.001  # même ordre de grandeur que continuation.py:MIN_TREND_SLOPE
DIAMOND_TREND_CONTEXT_BARS = MIN_PATTERN_BARS


def _diamond_slope_quality(slope, reference=MIN_DIAMOND_SLOPE):
    """Même formule que `continuation.py:_slope_quality` — dupliquée plutôt
    qu'importée, comme `_rsi_at_last`/`_macd_line_at_last` dans ce fichier
    (voir leur docstring : éviter un import croisé entre modules de
    détection indépendants)."""
    return float(np.clip(abs(slope) / (reference * 3), 0.0, 1.0))


def _diamond(df, bullish: bool) -> list[PatternMatch]:
    """Diamond Bottom (haussier) si `bullish`, Diamond Top (baissier) sinon.

    Sur les `DIAMOND_WINDOW` dernières barres, à l'exclusion de la toute
    dernière (la candidate à la cassure) : découpe le motif en 2 moitiés
    égales et calcule le range (haut-bas) de chaque barre. La 1re moitié
    doit avoir une pente positive (`relative_slope`) sur ces ranges
    (volatilité en expansion) et la 2e une pente négative (volatilité en
    contraction), toutes deux au-delà de `MIN_DIAMOND_SLOPE` en valeur
    absolue. Exige en plus que la tendance des `DIAMOND_TREND_CONTEXT_BARS`
    barres précédant la fenêtre aille dans le sens opposé au retournement
    attendu (haussière avant un Diamond Top, baissière avant un Diamond
    Bottom — même filtre dur que `candlestick.py:_preceding_trend`, mais
    exprimé ici via `relative_slope` plutôt qu'une classification up/down/
    flat à 3 états). Confirmée par une cassure de la dernière clôture de la
    fenêtre au-delà du plus haut/bas des clôtures de la 2e moitié du
    motif (hors barre de cassure elle-même)."""
    w = tail_window(df, DIAMOND_WINDOW)
    if len(w) < MIN_PATTERN_BARS * 2 + 1:
        return []
    pattern = w.iloc[:-1]
    ranges = (pattern["high"] - pattern["low"]).values
    n = len(ranges)
    mid = n // 2
    first_half, second_half = ranges[:mid], ranges[mid:]
    if len(first_half) < 2 or len(second_half) < 2:
        return []

    expansion_slope = relative_slope(first_half)
    contraction_slope = relative_slope(second_half)
    if expansion_slope < MIN_DIAMOND_SLOPE:
        return []
    if contraction_slope > -MIN_DIAMOND_SLOPE:
        return []

    # Tendance précédant la fenêtre (hors fenêtre elle-même), même principe
    # que `candlestick.py:_preceding_trend`.
    window_start_pos = len(df) - len(w)
    trend_end = window_start_pos
    trend_start = max(0, trend_end - DIAMOND_TREND_CONTEXT_BARS)
    preceding = df["close"].iloc[trend_start:trend_end]
    if len(preceding) < DIAMOND_TREND_CONTEXT_BARS // 2:
        return []
    preceding_slope = relative_slope(preceding.values)
    if bullish and preceding_slope >= -MIN_DIAMOND_SLOPE:
        return []
    if not bullish and preceding_slope <= MIN_DIAMOND_SLOPE:
        return []

    second_half_close = pattern["close"].iloc[mid:]
    last_close = w["close"].iloc[-1]
    if bullish:
        breakout_level = float(second_half_close.max())
        if last_close <= breakout_level * (1 + BREAKOUT_BUFFER):
            return []
    else:
        breakout_level = float(second_half_close.min())
        if last_close >= breakout_level * (1 - BREAKOUT_BUFFER):
            return []

    widest_range = float(np.max(ranges))
    geometry_quality = 0.5 * _diamond_slope_quality(expansion_slope) + 0.5 * _diamond_slope_quality(contraction_slope)
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=bullish)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=bullish)
    macd_conf = macd_confirmation(df["close"], len(df) - 1, bullish=bullish)

    return [
        PatternMatch(
            pattern_type="Diamond Bottom" if bullish else "Diamond Top",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
            context={
                "breakout_level": breakout_level,
                "second_half_low": float(second_half_close.min()),
                "second_half_high": float(second_half_close.max()),
                "widest_range": widest_range,
                "expansion_slope": round(float(expansion_slope), 5),
                "contraction_slope": round(float(contraction_slope), 5),
                "rsi_14": _rsi_at_last(df["close"]),
                "macd_line": _macd_line_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
                "macd_confirmation": round(float(macd_conf), 3),
            },
        )
    ]


def detect_diamond_bottom(df) -> list[PatternMatch]:
    return _diamond(df, bullish=True)


def detect_diamond_top(df) -> list[PatternMatch]:
    return _diamond(df, bullish=False)
