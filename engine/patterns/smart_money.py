"""Détecteurs "Smart Money Concepts" (école ICT) : Fair Value Gap (FVG),
Breakaway Gap (BAG), Order Block, Break of Structure (BOS).

Origine et fiabilité des sources : ce module fait suite à une passe de
documentation sur des captures d'écran issues des réseaux sociaux
(`George_Strategies_Images_Synthese.md`), de fiabilité inégale — certaines
images étaient contradictoires entre elles sur la géométrie exacte d'une
figure. Quand c'est le cas, ce fichier privilégie la définition standard/
source primaire plutôt que de tenter de reproduire fidèlement un schéma
ambigu. C'est explicitement le cas du Breakaway Gap (BAG) ci-dessous : voir
sa docstring dédiée pour le détail du choix (les schémas de la synthèse
n'étaient pas d'accord entre eux sur la géométrie exacte distinguant FVG et
BAG, donc la définition classique pré-ICT de l'analyse technique a été
retenue plutôt qu'un arbitrage arbitraire entre deux captures ambiguës).

Différence architecturale avec les figures chartistes classiques
(`reversal.py`/`continuation.py`/`breakout.py`) : le Fair Value Gap et
l'Order Block ne portent que sur une poignée de bougies très récentes (pas de
scan de tout l'historique via extrema locaux), à l'image des figures en
bougies japonaises de `candlestick.py`. Le Break of Structure, à l'inverse,
réutilise `local_maxima_idx`/`local_minima_idx` de `common.py` comme les
figures chartistes classiques, mais vise un objectif différent : la cassure
d'un point de structure isolé (un swing high/low), pas d'une figure
géométrique composée à plusieurs points.

Les 4 familles de ce fichier sont des figures "chart pattern" au sens de
`engine/confidence.py` : aucune ne calcule ni ne transmet de `stoch_conf` à
`confidence_score` (réservé aux bougies japonaises de `candlestick.py`, voir
sa docstring)."""

import numpy as np
import pandas as pd

from engine.confidence import confidence_score, macd_confirmation, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.breakout import MIN_TOUCHES as BREAKOUT_MIN_TOUCHES
from engine.patterns.breakout import WINDOW as BREAKOUT_WINDOW
from engine.patterns.common import (
    BREAKOUT_BUFFER,
    LEVEL_TOLERANCE,
    MIN_PATTERN_BARS,
    PatternMatch,
    local_maxima_idx,
    local_minima_idx,
    macd,
    rsi,
    tail_window,
)


def _rsi_at_last(close) -> float | None:
    """Même helper que `reversal.py`/`continuation.py`/`breakout.py`/
    `candlestick.py` — dupliqué plutôt qu'importé, voir leur docstring (éviter
    un import croisé entre modules de détection indépendants)."""
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)


def _macd_line_at_last(close) -> float | None:
    """Même helper que les autres modules de `engine/patterns/` — voir leur
    docstring."""
    macd_line, _, _ = macd(close)
    value = macd_line.iloc[-1]
    return None if pd.isna(value) else float(value)


def _score_and_match(df, pattern_type: str, geometry_quality: float, bullish: bool, extra_context: dict) -> list[PatternMatch]:
    """Même rôle que `candlestick.py:_score_and_match`, sans le facteur
    stochastique : les 4 familles de ce fichier sont des figures
    chartistes/structurelles, pas des bougies japonaises isolées (voir
    `engine/confidence.py:confidence_score` pour la redistribution du poids
    du stochastique quand `stoch_conf` est absent). Factorisé ici (à
    l'inverse de `reversal.py`/`continuation.py`/`breakout.py`, qui répètent
    ces lignes dans chaque détecteur) car les 8 détecteurs de ce fichier
    calculent tous exactement les mêmes 4 facteurs, sur le même modèle que
    `candlestick.py`."""
    close = df["close"]
    at_idx = len(close) - 1
    volume_conf = volume_confirmation(df["volume"], at_idx)
    trend_conf = trend_alignment(close, bullish=bullish)
    rsi_conf = rsi_confirmation(close, at_idx, bullish=bullish)
    macd_conf = macd_confirmation(close, at_idx, bullish=bullish)
    return [
        PatternMatch(
            pattern_type=pattern_type,
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
            context={
                "rsi_14": _rsi_at_last(close),
                "macd_line": _macd_line_at_last(close),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
                "macd_confirmation": round(float(macd_conf), 3),
                **extra_context,
            },
        )
    ]


# --- Fair Value Gap (FVG) --------------------------------------------------
#
# Définition ICT standard à 3 bougies, NON ambiguë (contrairement au BAG
# ci-dessous, où les schémas sources se contredisaient) : à la bougie t, un
# FVG haussier existe si le plus bas de la bougie t est strictement supérieur
# au plus haut de la bougie t-2 — un vide de prix "à l'intérieur" de la
# bougie t-1, jamais négocié dans le sens t-2 -> t. Le FVG baissier est le
# miroir exact. On exige en plus que les bougies t-1 ET t soient toutes deux
# haussières (resp. baissières) pour un FVG haussier (resp. baissier) : un
# vrai mouvement impulsif, pas un simple non-chevauchement accidentel dans un
# marché plat. Ne renvoie que le FVG tout juste formé sur la toute dernière
# bougie (t = len(df)-1) : par construction, un FVG qui vient de se former à
# l'instant n'a encore pu être "comblé" par aucune bougie ultérieure
# (il n'y en a pas) — pas de recherche historique de tous les FVG passés.


def _fair_value_gap(df, bullish: bool) -> list[PatternMatch]:
    n = len(df)
    if n < 3:
        return []
    t = n - 1
    c2, c1, c0 = df.iloc[t - 2], df.iloc[t - 1], df.iloc[t]

    if bullish:
        impulse = c1["close"] > c1["open"] and c0["close"] > c0["open"]
        gap_exists = c0["low"] > c2["high"]
    else:
        impulse = c1["close"] < c1["open"] and c0["close"] < c0["open"]
        gap_exists = c0["high"] < c2["low"]
    if not impulse or not gap_exists:
        return []

    gap_bottom = float(c2["high"]) if bullish else float(c0["high"])
    gap_top = float(c0["low"]) if bullish else float(c2["low"])
    mid_range = float(c1["high"] - c1["low"])
    # Netteté du gap : sa taille relativement au range complet de la bougie
    # médiane (celle "à l'intérieur" de laquelle le vide se forme) — un gap
    # qui occupe une large part du range de la bougie médiane est plus net
    # qu'un gap qui ne fait qu'effleurer la limite de non-chevauchement.
    geometry_quality = float(np.clip((gap_top - gap_bottom) / max(mid_range, 1e-9), 0.0, 1.0))

    return _score_and_match(
        df,
        "Bullish Fair Value Gap" if bullish else "Bearish Fair Value Gap",
        geometry_quality,
        bullish,
        {
            "gap_bottom": gap_bottom,
            "gap_top": gap_top,
            "gap_bar_index": t,
            "impulse_start": float(c2["open"]),
            "impulse_end": float(c0["close"]),
        },
    )


def detect_bullish_fair_value_gap(df) -> list[PatternMatch]:
    return _fair_value_gap(df, bullish=True)


def detect_bearish_fair_value_gap(df) -> list[PatternMatch]:
    return _fair_value_gap(df, bullish=False)


# --- Breakaway Gap (BAG) ---------------------------------------------------
#
# CHOIX VOLONTAIRE ET DOCUMENTÉ : la synthèse `George_Strategies_Images_
# Synthese.md` contenait deux schémas contradictoires sur la géométrie exacte
# distinguant le FVG (ci-dessus) du BAG — l'un plaçait le rectangle du BAG
# sur 2 bougies, l'autre sur 3, sans accord sur ses bornes exactes. Plutôt
# que d'arbitrer entre deux captures d'écran ambiguës de fiabilité douteuse,
# ce détecteur reprend la définition CLASSIQUE (pré-ICT) de l'analyse
# technique : un BAG est un vrai gap de PRIX (le plus bas du jour strictement
# supérieur au plus haut de la veille pour un BAG haussier — par opposition
# au FVG ci-dessus, qui n'exige qu'un non-chevauchement sur 3 bougies, jamais
# un vrai gap sur la bougie de confirmation elle-même), qui survient en
# cassant un range de consolidation récent déjà testé plusieurs fois (même
# logique de comptage de touches que `breakout.py:detect_breakout`/
# `detect_breakdown`, réutilisée ici via `BREAKOUT_WINDOW`/
# `BREAKOUT_MIN_TOUCHES` importés — pas redéfinis), confirmé par un volume
# sur la bougie de gap d'au moins `BAG_VOLUME_RATIO` fois la moyenne de la
# fenêtre de consolidation. Un BAG n'est donc PAS "un FVG qui serait aussi un
# vrai gap" : c'est une définition disjointe, qui exige en plus la cassure
# d'un range préalablement testé — une condition que le FVG ne pose jamais.

BAG_VOLUME_RATIO = 1.5


def _breakaway_gap(df, bullish: bool) -> list[PatternMatch]:
    w = tail_window(df, BREAKOUT_WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    prior, last_close = close.iloc[:-1], close.iloc[-1]
    last_row, prev_row = df.iloc[-1], df.iloc[-2]

    if bullish:
        level = prior.max()
        touches = int((prior >= level * (1 - LEVEL_TOLERANCE)).sum())
        if touches < BREAKOUT_MIN_TOUCHES:
            return []
        if last_close <= level * (1 + BREAKOUT_BUFFER):
            return []
        if not (last_row["low"] > prev_row["high"]):
            return []  # pas de vrai gap de prix (juste un non-chevauchement à 3 bougies : ce serait un FVG, pas un BAG)
        gap_bottom, gap_top = float(prev_row["high"]), float(last_row["low"])
        breakout_strength = (last_close - level) / level
    else:
        level = prior.min()
        touches = int((prior <= level * (1 + LEVEL_TOLERANCE)).sum())
        if touches < BREAKOUT_MIN_TOUCHES:
            return []
        if last_close >= level * (1 - BREAKOUT_BUFFER):
            return []
        if not (last_row["high"] < prev_row["low"]):
            return []
        gap_bottom, gap_top = float(last_row["high"]), float(prev_row["low"])
        breakout_strength = (level - last_close) / level

    baseline_volume = w["volume"].iloc[:-1].mean()
    gap_volume = float(df["volume"].iloc[-1])
    if pd.isna(baseline_volume) or baseline_volume == 0 or gap_volume < baseline_volume * BAG_VOLUME_RATIO:
        return []

    touch_quality = float(np.clip((touches - BREAKOUT_MIN_TOUCHES + 1) / (BREAKOUT_MIN_TOUCHES + 1), 0.0, 1.0))
    strength_quality = float(np.clip(breakout_strength / (BREAKOUT_BUFFER * 10), 0.0, 1.0))
    gap_quality = float(np.clip(((gap_top - gap_bottom) / level) / (BREAKOUT_BUFFER * 10), 0.0, 1.0))
    # Géométrie = qualité du palier testé (touches) + force de la cassure +
    # netteté du gap lui-même. Le facteur volume, bien que déterminant pour
    # la DÉFINITION du BAG (condition d'existence, pas de score), reste porté
    # séparément par `volume_conf` (poids dédié dans `confidence_score`) —
    # pas dupliqué ici dans la géométrie.
    geometry_quality = 0.4 * touch_quality + 0.3 * strength_quality + 0.3 * gap_quality

    level_key = "resistance" if bullish else "support"
    return _score_and_match(
        df,
        "Bullish Breakaway Gap" if bullish else "Bearish Breakaway Gap",
        geometry_quality,
        bullish,
        {
            level_key: float(level),
            "touches": touches,
            "gap_bottom": gap_bottom,
            "gap_top": gap_top,
            "gap_bar_index": len(df) - 1,
        },
    )


def detect_bullish_breakaway_gap(df) -> list[PatternMatch]:
    return _breakaway_gap(df, bullish=True)


def detect_bearish_breakaway_gap(df) -> list[PatternMatch]:
    return _breakaway_gap(df, bullish=False)


# --- Order Block ------------------------------------------------------------
#
# La dernière bougie de couleur opposée immédiatement avant un mouvement
# impulsif. Un candidat (bougie baissière pour un Order Block haussier,
# haussière pour un Order Block baissier) qualifie si, sur les
# `IMPULSE_WINDOW` bougies qui le suivent IMMÉDIATEMENT, le prix se déplace
# de plus de `IMPULSE_MIN_RETURN` dans le sens attendu sans qu'aucune clôture
# ne revienne sous (haussier) / au-dessus (baissier) du bas/haut de la bougie
# candidate elle-même (ce qui invaliderait la zone). Parmi tous les candidats
# valides, on retient le PLUS RÉCENT (recherche à rebours depuis l'avant-
# dernière bougie). La figure ne se confirme que lorsque le prix REVIENT
# tester cette zone sans l'invalider entre-temps — et, comme tous les autres
# détecteurs de ce projet, on ne confirme que si ce retest a lieu sur la
# toute dernière bougie disponible (pas une recherche de tous les retests
# historiques).

IMPULSE_WINDOW = 3
IMPULSE_MIN_RETURN = 0.03


def _order_block(df, bullish: bool) -> list[PatternMatch]:
    n = len(df)
    last_idx = n - 1
    if n < IMPULSE_WINDOW + 2:
        return []

    # Tableaux numpy plutôt que `df.iloc[i]` dans la boucle : ce détecteur
    # parcourt tout l'historique bougie par bougie, et l'accès ligne à ligne
    # pandas en faisait ~60 % du temps de `detect_all` (mesuré en préparant
    # le backtest walk-forward, `engine/backtest_detectors.py`). Mêmes règles,
    # mêmes résultats : les comparaisons avec NaN restent fausses comme dans
    # la version pandas, et `np.fmin`/`np.fmax` ignorent les NaN comme
    # `(serie < x).any()`.
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    # suffix_min[k] = plus petite clôture de k à la dernière bougie incluse.
    suffix_min = np.fmin.accumulate(closes[::-1])[::-1]
    suffix_max = np.fmax.accumulate(closes[::-1])[::-1]
    last_low, last_high = float(lows[last_idx]), float(highs[last_idx])

    for i in range(last_idx - 1, -1, -1):
        is_opposite_colored = (closes[i] < opens[i]) if bullish else (closes[i] > opens[i])
        if not is_opposite_colored:
            continue

        impulse_end = i + IMPULSE_WINDOW
        if impulse_end >= last_idx:
            continue  # pas assez de bougies après l'impulsion pour un retest distinct de l'impulsion elle-même
        impulse_closes = closes[i + 1 : impulse_end + 1]

        base_price = float(closes[i])
        ob_low, ob_high = float(lows[i]), float(highs[i])

        # Test du retest sur la bougie courante en premier : le moins cher,
        # et toutes les conditions sont cumulatives (l'ordre ne change rien).
        retested_now = (last_low <= ob_high) if bullish else (last_high >= ob_low)
        if not retested_now:
            continue

        if bullish:
            impulse_return = (float(impulse_closes[-1]) - base_price) / abs(base_price)
            if impulse_return <= IMPULSE_MIN_RETURN:
                continue
            if (impulse_closes < ob_low).any():
                continue  # une clôture est revenue sous le bas de l'OB pendant l'impulsion : zone déjà invalidée
        else:
            impulse_return = (base_price - float(impulse_closes[-1])) / abs(base_price)
            if impulse_return <= IMPULSE_MIN_RETURN:
                continue
            if (impulse_closes > ob_high).any():
                continue

        # Zone valide entre la fin de l'impulsion et la bougie courante :
        # aucune clôture ne doit avoir invalidé la zone depuis.
        if bullish and suffix_min[impulse_end + 1] < ob_low:
            continue
        if not bullish and suffix_max[impulse_end + 1] > ob_high:
            continue

        zone_size = max(ob_high - ob_low, 1e-9)
        impulse_quality = float(np.clip(impulse_return / (2 * IMPULSE_MIN_RETURN), 0.0, 1.0))
        # Profondeur du retest dans la zone (0 = simple effleurement du bord
        # le plus proche du prix courant, 1 = retest jusqu'au bord opposé ou
        # au-delà) — un retest franc dans la zone est un signal plus net
        # qu'un simple frôlement.
        if bullish:
            penetration = ob_high - last_low
        else:
            penetration = last_high - ob_low
        retest_quality = float(np.clip(penetration / zone_size, 0.0, 1.0))
        geometry_quality = 0.5 * impulse_quality + 0.5 * retest_quality

        impulse_amplitude = abs(float(impulse_closes[-1]) - base_price)

        return _score_and_match(
            df,
            "Bullish Order Block" if bullish else "Bearish Order Block",
            geometry_quality,
            bullish,
            {
                "ob_index": i,
                "ob_low": ob_low,
                "ob_high": ob_high,
                "impulse_end_index": impulse_end,
                "impulse_amplitude": impulse_amplitude,
                "retest_index": last_idx,
            },
        )
    return []


def detect_bullish_order_block(df) -> list[PatternMatch]:
    return _order_block(df, bullish=True)


def detect_bearish_order_block(df) -> list[PatternMatch]:
    return _order_block(df, bullish=False)


# --- Break of Structure (BOS) ----------------------------------------------
#
# Une clôture qui dépasse le dernier point de structure significatif (un
# sommet local pour un BOS haussier, un creux local pour un BOS baissier),
# trouvé via `local_maxima_idx`/`local_minima_idx` de `common.py`. Le point
# de structure retenu doit avoir au moins `MIN_PATTERN_BARS` séances
# d'ancienneté (un vrai point de structure antérieur, pas un extremum tout
# juste formé qui ne serait que du bruit). Conceptuellement proche de
# `breakout.py:detect_breakout`/`detect_breakdown`, mais la référence n'est
# pas un palier testé plusieurs fois : c'est un unique point pivot (extremum
# local), reflet direct de la lecture "structure de marché" de l'école ICT
# plutôt que d'un range de trading. Volontairement gardé distinct de
# `breakout.py` plutôt que d'en réutiliser les détecteurs.


def _break_of_structure(df, bullish: bool) -> list[PatternMatch]:
    close = df["close"]
    n = len(close)
    last_idx = n - 1
    if n < MIN_PATTERN_BARS + 1:
        return []

    extrema = local_maxima_idx(close.values) if bullish else local_minima_idx(close.values)
    eligible = extrema[extrema <= last_idx - MIN_PATTERN_BARS]
    if len(eligible) == 0:
        return []
    swing_idx = int(eligible[-1])
    swing_price = float(close.iloc[swing_idx])
    last_close = float(close.iloc[last_idx])

    if bullish:
        if last_close <= swing_price * (1 + BREAKOUT_BUFFER):
            return []
        breakout_strength = (last_close - swing_price) / swing_price
    else:
        if last_close >= swing_price * (1 - BREAKOUT_BUFFER):
            return []
        breakout_strength = (swing_price - last_close) / swing_price

    strength_quality = float(np.clip(breakout_strength / (BREAKOUT_BUFFER * 10), 0.0, 1.0))
    # Ancienneté du point de structure cassé, au-delà du minimum exigé de
    # `MIN_PATTERN_BARS` : un point plus ancien (donc plus "digéré" par le
    # marché) est une référence de structure plus significative qu'un
    # extremum tout juste éligible.
    age_quality = float(np.clip((last_idx - swing_idx) / (MIN_PATTERN_BARS * 2), 0.0, 1.0))
    geometry_quality = 0.6 * strength_quality + 0.4 * age_quality

    swing_key = "swing_high" if bullish else "swing_low"
    return _score_and_match(
        df,
        "Bullish Break of Structure" if bullish else "Bearish Break of Structure",
        geometry_quality,
        bullish,
        {swing_key: {"index": swing_idx, "price": swing_price}},
    )


def detect_bullish_break_of_structure(df) -> list[PatternMatch]:
    return _break_of_structure(df, bullish=True)


def detect_bearish_break_of_structure(df) -> list[PatternMatch]:
    return _break_of_structure(df, bullish=False)
