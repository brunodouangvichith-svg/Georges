"""Détecteurs Breakout / Breakdown : cassure d'un palier de
résistance/support horizontal testé plusieurs fois récemment.

Paramètres géométriques :

- ``WINDOW`` (20 barres) : fenêtre récente dans laquelle chercher le palier.
- ``MIN_TOUCHES`` (2) : nombre minimal de clôtures (avant la dernière barre)
  devant être à moins de ``LEVEL_TOLERANCE`` du niveau extrême de la fenêtre
  pour que ce niveau soit considéré comme un vrai palier testé, plutôt qu'un
  simple point isolé.

La barre juste avant la cassure doit elle-même être revenue sous (resp.
au-dessus) le palier d'au moins ``BREAKOUT_BUFFER`` : cela exclut les
tendances qui grimpent en continu (où la dernière clôture avant la fin de
fenêtre serait déjà au plus haut) et ne retient qu'une vraie figure
range-puis-cassure.
"""

import numpy as np
import pandas as pd

from engine.confidence import confidence_score, rsi_confirmation, trend_alignment, volume_confirmation
from engine.patterns.common import (
    BREAKOUT_BUFFER,
    LEVEL_TOLERANCE,
    MIN_PATTERN_BARS,
    PatternMatch,
    rsi,
    tail_window,
)


def _rsi_at_last(close) -> float | None:
    """Même helper que `reversal.py`/`continuation.py` — voir leur docstring."""
    value = rsi(close).iloc[-1]
    return None if pd.isna(value) else float(value)

WINDOW = 20
MIN_TOUCHES = 2


def detect_breakout(df) -> list[PatternMatch]:
    w = tail_window(df, WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    prior, last_close = close.iloc[:-1], close.iloc[-1]

    resistance = prior.max()
    touches = int((prior >= resistance * (1 - LEVEL_TOLERANCE)).sum())
    if touches < MIN_TOUCHES:
        return []
    if prior.iloc[-1] > resistance * (1 - BREAKOUT_BUFFER):
        return []  # pas de repli avant la cassure : grimpée continue, pas un vrai palier
    if last_close <= resistance * (1 + BREAKOUT_BUFFER):
        return []

    breakout_strength = (last_close - resistance) / resistance
    touch_quality = float(np.clip((touches - MIN_TOUCHES + 1) / (MIN_TOUCHES + 1), 0.0, 1.0))
    strength_quality = float(np.clip(breakout_strength / (BREAKOUT_BUFFER * 10), 0.0, 1.0))
    geometry_quality = 0.5 * touch_quality + 0.5 * strength_quality
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=True)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=True)

    return [
        PatternMatch(
            pattern_type="Breakout",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "resistance": float(resistance),
                "touches": touches,
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]


def detect_breakdown(df) -> list[PatternMatch]:
    w = tail_window(df, WINDOW)
    if len(w) < MIN_PATTERN_BARS:
        return []
    close = w["close"]
    prior, last_close = close.iloc[:-1], close.iloc[-1]

    support = prior.min()
    touches = int((prior <= support * (1 + LEVEL_TOLERANCE)).sum())
    if touches < MIN_TOUCHES:
        return []
    if prior.iloc[-1] < support * (1 + BREAKOUT_BUFFER):
        return []  # pas de rebond avant la cassure : chute continue, pas un vrai palier
    if last_close >= support * (1 - BREAKOUT_BUFFER):
        return []

    breakdown_strength = (support - last_close) / support
    touch_quality = float(np.clip((touches - MIN_TOUCHES + 1) / (MIN_TOUCHES + 1), 0.0, 1.0))
    strength_quality = float(np.clip(breakdown_strength / (BREAKOUT_BUFFER * 10), 0.0, 1.0))
    geometry_quality = 0.5 * touch_quality + 0.5 * strength_quality
    volume_conf = volume_confirmation(df["volume"], len(df) - 1)
    trend_conf = trend_alignment(df["close"], bullish=False)
    rsi_conf = rsi_confirmation(df["close"], len(df) - 1, bullish=False)

    return [
        PatternMatch(
            pattern_type="Breakdown",
            detected_at=df.index[-1],
            confidence=confidence_score(geometry_quality, volume_conf, trend_conf, rsi_conf),
            context={
                "support": float(support),
                "touches": touches,
                "rsi_14": _rsi_at_last(df["close"]),
                "geometry_quality": round(float(geometry_quality), 3),
                "volume_confirmation": round(float(volume_conf), 3),
                "trend_alignment": round(float(trend_conf), 3),
                "rsi_confirmation": round(float(rsi_conf), 3),
            },
        )
    ]
