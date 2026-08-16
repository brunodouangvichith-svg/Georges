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
calculer une confiance), distinct des facteurs `trend_conf`/`rsi_conf`/
`macd_conf` de `engine/confidence.py` qui, eux, continuent de pondérer la
confiance finale exactement comme pour les 13 détecteurs existants (même
architecture, mêmes poids GEOMETRY/VOLUME/TREND/RSI/MACD). Le stochastique
(`stoch_conf`) est en revanche spécifique à ce module : la synthèse Kabbaj
(§2.7/§4) ne le documente qu'en combinaison avec les bougies japonaises, donc
`confidence_score` ne le reçoit que d'ici (voir sa docstring pour comment son
poids est redistribué ailleurs).

Chaque paire de figures (marteau/pendu, marteau inversé/étoile filante) a la
**même géométrie**, seule la tendance précédente et le sens qui en découle
diffèrent — reflet direct de la façon dont le livre les présente. Avalement/
étoile/nuage-pénétrante ont leur sens déterminé par la couleur des bougies
elles-mêmes (haussière/baissière), la tendance précédente ne fait que
confirmer que le contexte est propice à un retournement.
"""

import numpy as np
import pandas as pd

from engine.confidence import (
    confidence_score,
    macd_confirmation,
    rsi_confirmation,
    stochastic_confirmation,
    trend_alignment,
    volume_confirmation,
)
from engine.patterns.common import PatternMatch, macd, relative_slope, rsi

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


def _macd_line_at_last(close) -> float | None:
    """Même helper que `reversal.py`/`continuation.py`/`breakout.py` — voir
    leur docstring."""
    macd_line, _, _ = macd(close)
    value = macd_line.iloc[-1]
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
    macd_conf = macd_confirmation(close, at_idx, bullish=bullish)
    # Stochastique : voir `engine/confidence.py:stochastic_confirmation` —
    # réservé aux bougies japonaises (§2.7/§4 de la synthèse Kabbaj), donc
    # calculé uniquement ici parmi les 22 détecteurs de `engine/patterns/`.
    stoch_conf = stochastic_confirmation(df["high"], df["low"], close, at_idx, bullish=bullish)
    return [
        PatternMatch(
            pattern_type=pattern_type,
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf, stoch_conf),
            context={
                "signal_index": signal_idx,
                "rsi_14": _rsi_at_last(close),
                "macd_line": _macd_line_at_last(close),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
                "macd_confirmation": round(float(macd_conf), 3),
                "stochastic_confirmation": round(float(stoch_conf), 3),
                **extra_context,
            },
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


# --- Harami haussier / baissier --------------------------------------------
#
# Contrairement à l'avalement (`detect_bullish_engulfing`/`detect_bearish_
# engulfing`), qui exige que le corps courant DÉPASSE le corps précédent, le
# Harami exige l'inclusion stricte inverse : une grande bougie suivie d'une
# petite bougie de couleur opposée dont le corps tient ENTIÈREMENT dans le
# corps de la précédente — une compression/indécision après un mouvement
# marqué, pas une domination.

HARAMI_MAX_BODY_RATIO = 0.6  # corps courant <= 60% du corps précédent, pour un "petit corps" significatif


def _harami(df, bullish: bool) -> list[PatternMatch]:
    """Harami haussier (`bullish`) : grande bougie baissière suivie d'une
    petite bougie haussière contenue dans son corps, après une tendance
    baissière. Harami baissier : symétrique (grande bougie haussière, petite
    bougie baissière contenue, après une tendance haussière). Le corps de la
    bougie courante doit à la fois être strictement contenu dans le corps
    précédent ET rester sous `HARAMI_MAX_BODY_RATIO` de sa taille — une
    inclusion à peine plus petite (ratio proche de 1) ne serait pas un
    vrai "petit corps"."""
    if len(df) < TREND_CONTEXT_BARS + 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if bullish:
        if not prev_m["bearish"] or not curr_m["bullish"]:
            return []
    else:
        if not prev_m["bullish"] or not curr_m["bearish"]:
            return []
    if prev_m["body"] == 0:
        return []
    prev_body_low, prev_body_high = min(prev["open"], prev["close"]), max(prev["open"], prev["close"])
    curr_body_low, curr_body_high = min(curr["open"], curr["close"]), max(curr["open"], curr["close"])
    if not (curr_body_low > prev_body_low and curr_body_high < prev_body_high):
        return []
    body_ratio = curr_m["body"] / prev_m["body"]
    if body_ratio > HARAMI_MAX_BODY_RATIO:
        return []
    if _preceding_trend(df, signal_bars=2) != ("down" if bullish else "up"):
        return []

    # Netteté géométrique : plus le corps courant est petit relativement au
    # corps précédent (ratio proche de 0), plus la compression/indécision est
    # marquée.
    geometry_quality = float(np.clip(1.0 - body_ratio / HARAMI_MAX_BODY_RATIO, 0.0, 1.0))
    return _score_and_match(
        df,
        "Bullish Harami" if bullish else "Bearish Harami",
        geometry_quality,
        bullish,
        len(df) - 1,
        {
            # Géométrie brute de la bougie-mère, nécessaire au calcul des
            # niveaux de sortie (son range sert de mouvement mesuré, ses
            # extrêmes servent de niveau d'invalidation structurel).
            "mother_index": len(df) - 2,
            "mother_high": float(prev["high"]),
            "mother_low": float(prev["low"]),
        },
    )


def detect_bullish_harami(df) -> list[PatternMatch]:
    return _harami(df, bullish=True)


def detect_bearish_harami(df) -> list[PatternMatch]:
    return _harami(df, bullish=False)


# --- Three White Soldiers / Three Black Crows -------------------------------

SOLDIER_MAX_SHADOW_RATIO = 0.5  # ombre de poursuite (haute pour Soldiers, basse pour Crows) <= 50% du corps
SOLDIER_MIN_BODY_RATIO = 0.6  # corps "long" (le "White"/"Black" du nom) >= 60% du range de la bougie


def _three_soldiers_or_crows(df, bullish: bool) -> list[PatternMatch]:
    """Trois bougies consécutives de même couleur, chacune ouvrant DANS le
    corps de la précédente et clôturant AU-DELÀ de la clôture précédente
    (progression continue, pas seulement 3 bougies de même sens), avec un
    corps "long" (>= `SOLDIER_MIN_BODY_RATIO` du range de la bougie — c'est
    le "White"/"Black" du nom, pas juste 3 clôtures dans le même sens) et une
    ombre de poursuite (haute pour les 3 Soldats, basse pour les 3 Corbeaux)
    limitée à `SOLDIER_MAX_SHADOW_RATIO` du corps de chaque bougie — écarte
    une "fausse" série où une longue mèche mange l'essentiel du mouvement.
    L'ombre opposée (basse pour les Soldats, haute pour les Corbeaux) est
    plafonnée à la même limite : sans les deux gardes-fous du corps ET de
    l'ombre opposée, 3 bougies à corps minuscule flanquées d'une grande mèche
    du côté non contraint passaient tous les tests existants et étaient
    détectées comme "Three White Soldiers" — un vrai faux positif trouvé en
    révision, rien à voir visuellement avec 3 longues bougies vertes.
    Three White Soldiers accepte un contexte précédent baissier OU plat
    (retournement ou simple reprise après une pause) ; Three Black Crows
    exige une tendance haussière précédente (retournement uniquement — le
    livre ne documente pas de variante "de continuation" pour les corbeaux)."""
    if len(df) < TREND_CONTEXT_BARS + 3:
        return []
    candles = [df.iloc[-3], df.iloc[-2], df.iloc[-1]]
    metrics = [_candle_metrics(c) for c in candles]
    if bullish:
        if not all(m["bullish"] for m in metrics):
            return []
    else:
        if not all(m["bearish"] for m in metrics):
            return []
    if any(m["body"] == 0 or m["range"] == 0 for m in metrics):
        return []
    if any(m["body"] / m["range"] < SOLDIER_MIN_BODY_RATIO for m in metrics):
        return []

    for prev, curr in zip(candles, candles[1:]):
        prev_body_low, prev_body_high = min(prev["open"], prev["close"]), max(prev["open"], prev["close"])
        if not (prev_body_low <= curr["open"] <= prev_body_high):
            return []
        if bullish and curr["close"] <= prev["close"]:
            return []
        if not bullish and curr["close"] >= prev["close"]:
            return []

    shadow_ratios = []
    for m in metrics:
        trailing_shadow = m["upper_shadow"] if bullish else m["lower_shadow"]
        leading_shadow = m["lower_shadow"] if bullish else m["upper_shadow"]
        trailing_ratio = trailing_shadow / m["body"]
        leading_ratio = leading_shadow / m["body"]
        if trailing_ratio > SOLDIER_MAX_SHADOW_RATIO or leading_ratio > SOLDIER_MAX_SHADOW_RATIO:
            return []
        shadow_ratios.append(trailing_ratio)

    if bullish:
        if _preceding_trend(df, signal_bars=3) not in ("down", "flat"):
            return []
    else:
        if _preceding_trend(df, signal_bars=3) != "up":
            return []

    # Netteté géométrique : moyenne, sur les 3 bougies, de la qualité de
    # l'ombre de poursuite (plus elle est petite relativement au corps, plus
    # la conviction directionnelle est nette).
    shadow_quality = float(np.mean([np.clip(1.0 - r / SOLDIER_MAX_SHADOW_RATIO, 0.0, 1.0) for r in shadow_ratios]))
    geometry_quality = shadow_quality

    first, last = candles[0], candles[-1]
    extra_context = {
        # Géométrie brute de la formation entière (hors bougie de signal
        # seule) : nécessaire au calcul du mouvement mesuré (`net_move`) et du
        # niveau d'invalidation structurel (`formation_low`/`formation_high`).
        "formation_start": {"index": len(df) - 3, "price": float(first["open"])},
        "formation_low": float(min(c["low"] for c in candles)),
        "formation_high": float(max(c["high"] for c in candles)),
        "net_move": float(last["close"] - first["open"]),
    }
    return _score_and_match(
        df,
        "Three White Soldiers" if bullish else "Three Black Crows",
        geometry_quality,
        bullish,
        len(df) - 1,
        extra_context,
    )


def detect_three_white_soldiers(df) -> list[PatternMatch]:
    return _three_soldiers_or_crows(df, bullish=True)


def detect_three_black_crows(df) -> list[PatternMatch]:
    return _three_soldiers_or_crows(df, bullish=False)


# --- Kicker haussier / baissier ---------------------------------------------

KICKER_MIN_GAP_RATIO = 0.05  # échelle de référence (relative au range précédent) pour noter l'ampleur du gap


def _kicker(df, bullish: bool) -> list[PatternMatch]:
    """Bougie de couleur opposée à la précédente, séparée par un gap TOTAL —
    aucun recouvrement d'amplitude (range haut-bas), pas seulement de corps :
    pour un Kicker haussier, le plus bas de la bougie courante dépasse
    strictement le plus haut de la précédente ; pour un Kicker baissier,
    l'inverse. C'est ce zéro-recouvrement strict qui distingue le Kicker de
    l'avalement (`detect_bullish_engulfing`/`detect_bearish_engulfing`), où
    les amplitudes se chevauchent toujours par construction. Signal jugé
    suffisamment fort par lui-même (retournement brutal et immédiat du
    sentiment, typiquement une nouvelle choc) pour ne pas exiger de tendance
    précédente particulière, contrairement aux figures ci-dessus."""
    if len(df) < 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_m, curr_m = _candle_metrics(prev), _candle_metrics(curr)
    if bullish:
        if not prev_m["bearish"] or not curr_m["bullish"]:
            return []
        if not (curr["low"] > prev["high"]):
            return []
        gap = float(curr["low"] - prev["high"])
        gap_low, gap_high = float(prev["high"]), float(curr["low"])
    else:
        if not prev_m["bullish"] or not curr_m["bearish"]:
            return []
        if not (curr["high"] < prev["low"]):
            return []
        gap = float(prev["low"] - curr["high"])
        gap_low, gap_high = float(curr["high"]), float(prev["low"])

    prev_range = prev_m["range"] or 1e-9
    gap_ratio = gap / prev_range
    geometry_quality = float(np.clip(gap_ratio / (2 * KICKER_MIN_GAP_RATIO), 0.0, 1.0))
    return _score_and_match(
        df,
        "Bullish Kicker" if bullish else "Bearish Kicker",
        geometry_quality,
        bullish,
        len(df) - 1,
        {
            # Bornes brutes du gap lui-même, nécessaires au calcul du niveau
            # de sortie (stop au bord du gap le plus proche de l'entrée).
            "gap_low": gap_low,
            "gap_high": gap_high,
        },
    )


def detect_bullish_kicker(df) -> list[PatternMatch]:
    return _kicker(df, bullish=True)


def detect_bearish_kicker(df) -> list[PatternMatch]:
    return _kicker(df, bullish=False)


# --- Dragonfly Doji ----------------------------------------------------------


def _dragonfly_doji_shape(df) -> dict | None:
    if len(df) < TREND_CONTEXT_BARS + 1:
        return None
    m = _candle_metrics(df.iloc[-1])
    if m["range"] == 0 or m["body"] == 0:
        return None
    if m["body"] / m["range"] > DOJI_MAX_BODY_RATIO:
        return None
    # Reprend telles quelles les ratios déjà utilisés par `_hammer_shape`
    # (ombre longue >= LONG_SHADOW_MIN_RATIO x corps, ombre courte <=
    # SHORT_SHADOW_MAX_RATIO x corps), simplement appliqués ici à un corps
    # quasi nul (doji) plutôt qu'à un petit corps (marteau) — même
    # vocabulaire de forme, cohérent avec le reste du fichier.
    if m["lower_shadow"] < m["body"] * LONG_SHADOW_MIN_RATIO:
        return None
    if m["upper_shadow"] > m["body"] * SHORT_SHADOW_MAX_RATIO:
        return None
    return m


def detect_dragonfly_doji(df) -> list[PatternMatch]:
    """Doji en "T" : corps quasi nul (`DOJI_MAX_BODY_RATIO`) posé en haut du
    range, longue mèche basse et mèche haute négligeable — signal de
    retournement haussier, exige une tendance baissière précédente (même
    logique que le Doji haussier générique ci-dessus, jamais un signal
    isolé — §2.1 de la synthèse). Variante plus spécifique du Doji : toute
    Dragonfly Doji est un Doji, l'inverse n'est pas vrai."""
    m = _dragonfly_doji_shape(df)
    if m is None or _preceding_trend(df) != "down":
        return []
    geometry_quality = float(np.clip(m["lower_shadow"] / (m["body"] * LONG_SHADOW_MIN_RATIO * 1.5), 0.0, 1.0))
    return _score_and_match(df, "Dragonfly Doji", geometry_quality, True, len(df) - 1, {})


# --- Marubozu haussier / baissier --------------------------------------------

MARUBOZU_MAX_SHADOW_RATIO = 0.05  # ombre haute ET basse <= 5% du range : bougie "pleine"


def _marubozu(df, bullish: bool) -> list[PatternMatch]:
    """Bougie "pleine" : ouverture au ras du plus bas et clôture au ras du
    plus haut (haussier), ou l'inverse (baissier) — les deux ombres restent
    sous `MARUBOZU_MAX_SHADOW_RATIO` du range. Signal de conviction forte,
    pas structurellement un retournement (contrairement au marteau/Harami/
    Doji ci-dessus, qui ont besoin d'un "avant" à retourner) : aucune
    tendance précédente particulière n'est exigée ici — la bougie se suffit
    à elle-même. `trend_conf`/`rsi_conf`/`macd_conf`/`stoch_conf` continuent
    néanmoins d'être calculés normalement contre le sens de la bougie, comme
    pour toutes les figures de ce module."""
    if len(df) < 1:
        return []
    row = df.iloc[-1]
    m = _candle_metrics(row)
    if m["range"] == 0:
        return []
    threshold = m["range"] * MARUBOZU_MAX_SHADOW_RATIO
    if bullish:
        if not m["bullish"]:
            return []
        open_shadow = row["open"] - row["low"]
        close_shadow = row["high"] - row["close"]
    else:
        if not m["bearish"]:
            return []
        open_shadow = row["high"] - row["open"]
        close_shadow = row["close"] - row["low"]
    if open_shadow > threshold or close_shadow > threshold:
        return []

    max_ratio = max(open_shadow, close_shadow) / m["range"]
    geometry_quality = float(np.clip(1.0 - max_ratio / MARUBOZU_MAX_SHADOW_RATIO, 0.0, 1.0))
    return _score_and_match(
        df,
        "Bullish Marubozu" if bullish else "Bearish Marubozu",
        geometry_quality,
        bullish,
        len(df) - 1,
        {},
    )


def detect_bullish_marubozu(df) -> list[PatternMatch]:
    return _marubozu(df, bullish=True)


def detect_bearish_marubozu(df) -> list[PatternMatch]:
    return _marubozu(df, bullish=False)


# --- Inside Bar Breakout (haussier / baissier) -------------------------------


def _inside_bar_breakout(df, bullish: bool) -> list[PatternMatch]:
    """Trois bougies : la "mother bar" (barre-mère), une "inside bar" dont
    tout le range (haut-bas, pas seulement le corps) est contenu dans celui
    de la mother bar, puis une bougie de cassure dont la clôture dépasse le
    plus haut (haussier) ou le plus bas (baissier) de l'inside bar. Regarde 3
    barres en arrière depuis la barre de confirmation — contrairement aux
    autres figures de ce module (1 à 3 bougies, toujours en partant de la
    dernière), la bougie de signal ici n'est ni la mother bar ni l'inside
    bar, mais la cassure qui les suit. Pas de filtre de tendance précédente :
    la compression (mother bar -> inside bar, resserrement de la
    volatilité) est elle-même le signal d'indécision, la cassure en
    détermine seulement le sens."""
    if len(df) < 3:
        return []
    mother, inside, breakout = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if not (inside["high"] < mother["high"] and inside["low"] > mother["low"]):
        return []
    mother_range = float(mother["high"] - mother["low"])
    inside_range = float(inside["high"] - inside["low"])
    if mother_range <= 0 or inside_range <= 0:
        return []
    if bullish:
        if not (breakout["close"] > inside["high"]):
            return []
        breakout_strength = (breakout["close"] - inside["high"]) / inside_range
    else:
        if not (breakout["close"] < inside["low"]):
            return []
        breakout_strength = (inside["low"] - breakout["close"]) / inside_range

    # Netteté géométrique : compression de l'inside bar dans la mother bar
    # (plus son range est petit relativement à la mother bar, plus
    # l'indécision précédant la cassure est marquée) + vigueur de la cassure
    # elle-même (relative au range de l'inside bar).
    compression_quality = float(np.clip(1.0 - inside_range / mother_range, 0.0, 1.0))
    strength_quality = float(np.clip(breakout_strength, 0.0, 1.0))
    geometry_quality = 0.5 * compression_quality + 0.5 * strength_quality
    return _score_and_match(
        df,
        "Bullish Inside Bar" if bullish else "Bearish Inside Bar",
        geometry_quality,
        bullish,
        len(df) - 1,
        {
            # Géométrie brute de la mother bar et de l'inside bar, nécessaire
            # au calcul des niveaux de sortie (range de la mother bar comme
            # mouvement mesuré, son extrême opposé comme invalidation).
            "mother_index": len(df) - 3,
            "mother_high": float(mother["high"]),
            "mother_low": float(mother["low"]),
            "inside_index": len(df) - 2,
            "inside_high": float(inside["high"]),
            "inside_low": float(inside["low"]),
        },
    )


def detect_bullish_inside_bar(df) -> list[PatternMatch]:
    return _inside_bar_breakout(df, bullish=True)


def detect_bearish_inside_bar(df) -> list[PatternMatch]:
    return _inside_bar_breakout(df, bullish=False)


# --- Outside Bar (haussier / baissier) ---------------------------------------

OUTSIDE_BAR_CLOSE_THIRD = 1 / 3  # tiers haut (haussier) / bas (baissier) du range exigé pour la clôture


def _outside_bar(df, bullish: bool) -> list[PatternMatch]:
    """Bougie dont le range englobe ENTIÈREMENT celui de la précédente (plus
    haut au-dessus ET plus bas en dessous — pas seulement le corps, comme
    l'avalement). Le sens est donné par où clôture cette bougie dans son
    propre range : tiers supérieur pour un Outside Bar haussier (achat
    massif malgré l'élargissement du range, absorption des vendeurs), tiers
    inférieur pour un baissier. Pas de filtre de tendance précédente, comme
    le Kicker/Marubozu ci-dessus : l'engloutissement du range combiné à une
    clôture extrême est déjà, à lui seul, le signal."""
    if len(df) < 2:
        return []
    prev, curr = df.iloc[-2], df.iloc[-1]
    if not (curr["high"] > prev["high"] and curr["low"] < prev["low"]):
        return []
    curr_range = float(curr["high"] - curr["low"])
    prev_range = float(prev["high"] - prev["low"])
    if curr_range <= 0:
        return []
    close_position = (curr["close"] - curr["low"]) / curr_range
    if bullish:
        if close_position < 1 - OUTSIDE_BAR_CLOSE_THIRD:
            return []
        position_quality = (close_position - (1 - OUTSIDE_BAR_CLOSE_THIRD)) / OUTSIDE_BAR_CLOSE_THIRD
    else:
        if close_position > OUTSIDE_BAR_CLOSE_THIRD:
            return []
        position_quality = (OUTSIDE_BAR_CLOSE_THIRD - close_position) / OUTSIDE_BAR_CLOSE_THIRD

    # Netteté géométrique : extrémité de la position de clôture dans son
    # propre range (moitié) + ampleur de l'engloutissement par rapport au
    # range précédent (moitié) — les deux dimensions du signal.
    engulf_ratio = curr_range / max(prev_range, 1e-9)
    strength_quality = float(np.clip(engulf_ratio - 1.0, 0.0, 1.0))
    geometry_quality = 0.5 * float(np.clip(position_quality, 0.0, 1.0)) + 0.5 * strength_quality
    return _score_and_match(
        df,
        "Bullish Outside Bar" if bullish else "Bearish Outside Bar",
        geometry_quality,
        bullish,
        len(df) - 1,
        {
            # Géométrie brute de la bougie englobante et de la précédente,
            # nécessaire au calcul des niveaux de sortie (son propre range
            # comme mouvement mesuré, son extrême opposé comme invalidation).
            "outside_high": float(curr["high"]),
            "outside_low": float(curr["low"]),
            "prev_high": float(prev["high"]),
            "prev_low": float(prev["low"]),
        },
    )


def detect_bullish_outside_bar(df) -> list[PatternMatch]:
    return _outside_bar(df, bullish=True)


def detect_bearish_outside_bar(df) -> list[PatternMatch]:
    return _outside_bar(df, bullish=False)
