"""Niveaux de sortie proposés (take-profit / stop-loss) pour une figure
détectée — Phase 6, tâche 1.

Formule générale, appliquée à chacun des 13 types de `engine/patterns/`:
- **take-profit** = prix d'entrée ± un "mouvement mesuré" dérivé de la
  géométrie propre à la figure (ex. amplitude d'un double creux, hauteur du
  mât d'un drapeau — les deux exemples cités par la roadmap).
- **stop-loss** = le niveau d'invalidation de la figure (le support/
  résistance dont une cassure inverse annulerait la lecture technique), avec
  la même marge `BREAKOUT_BUFFER` que celle qui a validé la cassure d'entrée
  à la détection.

Pour les figures de retournement (Double Bottom/Top, Head & Shoulders et
inverse, Cup & Handle), toute la géométrie nécessaire est déjà dans
`context` (voir `engine/patterns/reversal.py`). Pour les figures de
continuation (triangles, biseaux) et Breakout/Breakdown, `context` ne garde
qu'une pente ou un pourcentage (voir `engine/patterns/continuation.py` et
`breakout.py`) — la hauteur de la figure est donc recalculée ici à partir de
l'historique de prix `df` déjà chargé, sur la même fenêtre que le détecteur
(`WINDOW`), plutôt que dupliquée dans `context` uniquement pour cet usage.

Module pur (pas d'accès DB) — testé sur des contextes synthétiques dans
`tests/test_exit_levels.py`, sur le même principe que `engine/backtest.py`.
"""
from __future__ import annotations

import pandas as pd

from engine.patterns.breakout import WINDOW as BREAKOUT_WINDOW
from engine.patterns.common import BREAKOUT_BUFFER
from engine.patterns.continuation import WINDOW as TRIANGLE_WEDGE_WINDOW

BULLISH_PATTERNS = {
    "Double Bottom",
    "Inverse Head & Shoulders",
    "Cup & Handle",
    "Ascending Triangle",
    "Falling Wedge",
    "Bull Flag",
    "Breakout",
}
BEARISH_PATTERNS = {
    "Double Top",
    "Head & Shoulders",
    "Descending Triangle",
    "Rising Wedge",
    "Bear Flag",
    "Breakdown",
}


def is_bullish(pattern_type: str) -> bool:
    """Lève `KeyError` pour un type inconnu — les 13 types de
    `engine/patterns/__init__.py:DETECTORS` doivent tous être classés."""
    if pattern_type in BULLISH_PATTERNS:
        return True
    if pattern_type in BEARISH_PATTERNS:
        return False
    raise KeyError(f"Type de figure non classé bullish/bearish : {pattern_type}")


def _recent_low(df: pd.DataFrame, window: int) -> float:
    return float(df["close"].iloc[-window:].min())


def _recent_high(df: pd.DataFrame, window: int) -> float:
    return float(df["close"].iloc[-window:].max())


def _double_bottom(context, entry_price, df):
    resistance = context["resistance"]["price"]
    lowest_bottom = min(context["bottom_1"]["price"], context["bottom_2"]["price"])
    depth = resistance - lowest_bottom
    return entry_price + depth, lowest_bottom * (1 - BREAKOUT_BUFFER)


def _double_top(context, entry_price, df):
    support = context["support"]["price"]
    highest_top = max(context["top_1"]["price"], context["top_2"]["price"])
    depth = highest_top - support
    return entry_price - depth, highest_top * (1 + BREAKOUT_BUFFER)


def _head_and_shoulders(context, entry_price, df):
    neckline = context["neckline"]["price"]
    depth = context["head"]["price"] - neckline
    return entry_price - depth, context["right_shoulder"]["price"] * (1 + BREAKOUT_BUFFER)


def _inverse_head_and_shoulders(context, entry_price, df):
    neckline = context["neckline"]["price"]
    depth = neckline - context["head"]["price"]
    return entry_price + depth, context["right_shoulder"]["price"] * (1 - BREAKOUT_BUFFER)


def _cup_and_handle(context, entry_price, df):
    rim = max(context["left_rim"]["price"], context["right_rim"]["price"])
    depth = rim - context["cup_bottom"]["price"]
    return entry_price + depth, context["handle_low"] * (1 - BREAKOUT_BUFFER)


def _ascending_triangle(context, entry_price, df):
    resistance = context["resistance"]
    support = _recent_low(df, TRIANGLE_WEDGE_WINDOW)
    depth = resistance - support
    return entry_price + depth, support * (1 - BREAKOUT_BUFFER)


def _descending_triangle(context, entry_price, df):
    support = context["support"]
    resistance = _recent_high(df, TRIANGLE_WEDGE_WINDOW)
    depth = resistance - support
    return entry_price - depth, resistance * (1 + BREAKOUT_BUFFER)


def _falling_wedge(context, entry_price, df):
    low = _recent_low(df, TRIANGLE_WEDGE_WINDOW)
    high = _recent_high(df, TRIANGLE_WEDGE_WINDOW)
    depth = high - low
    return entry_price + depth, low * (1 - BREAKOUT_BUFFER)


def _rising_wedge(context, entry_price, df):
    low = _recent_low(df, TRIANGLE_WEDGE_WINDOW)
    high = _recent_high(df, TRIANGLE_WEDGE_WINDOW)
    depth = high - low
    return entry_price - depth, high * (1 + BREAKOUT_BUFFER)


def _bull_flag(context, entry_price, df):
    return entry_price + context["pole_amplitude"], context["flag_low"] * (1 - BREAKOUT_BUFFER)


def _bear_flag(context, entry_price, df):
    return entry_price - context["pole_amplitude"], context["flag_high"] * (1 + BREAKOUT_BUFFER)


def _breakout(context, entry_price, df):
    resistance = context["resistance"]
    support = _recent_low(df, BREAKOUT_WINDOW)
    depth = resistance - support
    return entry_price + depth, resistance * (1 - BREAKOUT_BUFFER)


def _breakdown(context, entry_price, df):
    support = context["support"]
    resistance = _recent_high(df, BREAKOUT_WINDOW)
    depth = resistance - support
    return entry_price - depth, support * (1 + BREAKOUT_BUFFER)


_LEVEL_FUNCTIONS = {
    "Double Bottom": _double_bottom,
    "Double Top": _double_top,
    "Head & Shoulders": _head_and_shoulders,
    "Inverse Head & Shoulders": _inverse_head_and_shoulders,
    "Cup & Handle": _cup_and_handle,
    "Ascending Triangle": _ascending_triangle,
    "Descending Triangle": _descending_triangle,
    "Falling Wedge": _falling_wedge,
    "Rising Wedge": _rising_wedge,
    "Bull Flag": _bull_flag,
    "Bear Flag": _bear_flag,
    "Breakout": _breakout,
    "Breakdown": _breakdown,
}


def propose_levels(pattern_type: str, context: dict, entry_price: float, df: pd.DataFrame) -> tuple[float, float]:
    """Renvoie `(take_profit, stop_loss)` proposés pour cette figure. Lève
    `KeyError` si `pattern_type` n'est pas géré (ne devrait pas arriver : les
    13 types de `engine/patterns/__init__.py:DETECTORS` sont tous couverts)."""
    return _LEVEL_FUNCTIONS[pattern_type](context, entry_price, df)
