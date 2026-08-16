"""Détecteur Golden Cross / Death Cross — croisement SMA50/SMA200.

Différence architecturale majeure avec les autres familles de
`engine/patterns/` : ceci n'est PAS une figure géométrique lue sur les
chandeliers OHLC (un double creux, une tête-épaules, un marteau...), mais un
**événement de croisement entre deux séries dérivées** (deux moyennes
mobiles). Il n'y a ni extrema locaux à apparier, ni corps/ombre de bougie à
mesurer : la seule géométrie est la position relative de `sma50` par rapport
à `sma200`, bar par bar. C'est aussi, par construction, un détecteur
d'**événement** et non d'**état** : `sma50 > sma200` peut rester vrai pendant
des mois après un Golden Cross, mais la figure ne doit se déclencher qu'une
seule fois, la barre exacte où le croisement se produit — sinon un seul vrai
croisement produirait des centaines de détections identiques tant que la
tendance haussière dure.

Golden Cross (haussier) : `sma50` était <= `sma200` à la barre précédente et
`sma50` > `sma200` à la dernière barre. Death Cross (baissier) : le miroir.
Exige au moins `SMA_LONG + 1` barres d'historique (`SMA_LONG` pour que
`sma200` soit défini à la barre précédente, +1 pour disposer de cette barre
précédente elle-même — voir `common.py:sma`, `min_periods=window`).
"""

import pandas as pd

from engine.confidence import confidence_score, macd_confirmation, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.common import PatternMatch, macd, prominence_score, relative_diff, rsi, sma

# Dupliquées ici plutôt qu'importées de `engine/confidence.py` (qui définit
# les mêmes valeurs sous les mêmes noms pour `trend_alignment`) — même
# convention de duplication que `_rsi_at_last`/`_macd_line_at_last` dans
# `reversal.py`/`continuation.py`/`candlestick.py` : éviter un import croisé
# entre modules de détection indépendants.
SMA_SHORT = 50
SMA_LONG = 200

# Écart relatif sma50/sma200 à partir duquel un croisement est considéré
# "franc" plutôt que marginal (une clôture qui fait à peine basculer le
# signe) — même ordre de grandeur que `LEVEL_TOLERANCE` dans `common.py`.
CROSSOVER_STRENGTH_REFERENCE = 0.01


def _rsi_at_last(close) -> float | None:
    """Même helper que `reversal.py`/`continuation.py`/`candlestick.py` —
    dupliqué plutôt qu'importé, voir leur docstring."""
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)


def _macd_line_at_last(close) -> float | None:
    """Même helper que les autres modules de `engine/patterns/`."""
    macd_line, _, _ = macd(close)
    value = macd_line.iloc[-1]
    return None if pd.isna(value) else float(value)


def _crossover(df, bullish: bool) -> list[PatternMatch]:
    """Golden Cross (`bullish=True`) ou Death Cross (`bullish=False`).

    Géométrie : soit `d = sma50 - sma200`. Golden Cross si `d` passe de <= 0
    (barre précédente) à > 0 (dernière barre) ; Death Cross si `d` passe de
    >= 0 à < 0. `geometry_quality` mesure la netteté du croisement — l'écart
    relatif entre `sma50` et `sma200` à la barre de croisement, via
    `prominence_score` : un croisement qui ne fait que "toucher" (`d`
    infinitésimal) vaut une qualité proche de 0, un croisement où `sma50` a
    déjà nettement dépassé `sma200` (au moins `CROSSOVER_STRENGTH_REFERENCE`
    x2 d'écart relatif) vaut 1.0 — simplification assumée : elle ne regarde
    que l'écart final, pas la vitesse de convergence des deux moyennes avant
    le croisement.

    Note : `trend_alignment` (SMA50 vs SMA200, prix vs SMA50 — voir
    `engine/confidence.py`) lira typiquement une valeur proche de 1.0 juste
    après un croisement frais, par construction (la condition même du
    Golden/Death Cross recoupe directement celle de `trend_alignment`) —
    attendu, pas un bug de double-comptage : `trend_conf` reste une
    composante parmi 5 dans `confidence_score`, jamais la seule."""
    close = df["close"]
    if len(close) < SMA_LONG + 1:
        return []

    sma50 = sma(close, SMA_SHORT)
    sma200 = sma(close, SMA_LONG)
    prev50, prev200 = sma50.iloc[-2], sma200.iloc[-2]
    curr50, curr200 = sma50.iloc[-1], sma200.iloc[-1]
    if pd.isna(prev50) or pd.isna(prev200) or pd.isna(curr50) or pd.isna(curr200):
        return []

    if bullish:
        crossed = prev50 <= prev200 and curr50 > curr200
    else:
        crossed = prev50 >= prev200 and curr50 < curr200
    if not crossed:
        return []

    geometry_quality = prominence_score(relative_diff(curr50, curr200), CROSSOVER_STRENGTH_REFERENCE)
    at_idx = len(close) - 1
    volume_conf = volume_confirmation(df["volume"], at_idx)
    trend_conf = trend_alignment(close, bullish=bullish)
    rsi_conf = rsi_confirmation(close, at_idx, bullish=bullish)
    macd_conf = macd_confirmation(close, at_idx, bullish=bullish)

    return [
        PatternMatch(
            pattern_type="Golden Cross" if bullish else "Death Cross",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf, macd_conf),
            context={
                "sma50": float(curr50),
                "sma200": float(curr200),
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


def detect_golden_cross(df) -> list[PatternMatch]:
    return _crossover(df, bullish=True)


def detect_death_cross(df) -> list[PatternMatch]:
    return _crossover(df, bullish=False)
