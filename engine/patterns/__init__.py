from engine.patterns.breakout import detect_breakdown, detect_breakout
from engine.patterns.candlestick import (
    detect_bearish_doji,
    detect_bearish_engulfing,
    detect_bullish_doji,
    detect_bullish_engulfing,
    detect_dark_cloud_cover,
    detect_evening_star,
    detect_hammer,
    detect_hanging_man,
    detect_inverted_hammer,
    detect_morning_star,
    detect_piercing_line,
    detect_shooting_star,
)
from engine.patterns.common import PatternMatch
from engine.patterns.continuation import (
    detect_ascending_triangle,
    detect_bear_flag,
    detect_bull_flag,
    detect_descending_triangle,
    detect_falling_wedge,
    detect_rising_wedge,
)
from engine.patterns.reversal import (
    detect_cup_and_handle,
    detect_double_bottom,
    detect_double_top,
    detect_head_and_shoulders,
    detect_inverse_head_and_shoulders,
)

# Registre des détecteurs, chacun testable indépendamment (voir
# tests/test_patterns.py, tests/test_candlestick.py) et appelé par
# `engine.detect.detect_all`. 13 figures chartistes (Phase 1) + 12 figures en
# bougies japonaises (ad hoc, voir George_AnalyseTechnique_Kabbaj_Synthese.md).
DETECTORS = {
    "Double Bottom": detect_double_bottom,
    "Double Top": detect_double_top,
    "Cup & Handle": detect_cup_and_handle,
    "Head & Shoulders": detect_head_and_shoulders,
    "Inverse Head & Shoulders": detect_inverse_head_and_shoulders,
    "Bull Flag": detect_bull_flag,
    "Bear Flag": detect_bear_flag,
    "Ascending Triangle": detect_ascending_triangle,
    "Descending Triangle": detect_descending_triangle,
    "Falling Wedge": detect_falling_wedge,
    "Rising Wedge": detect_rising_wedge,
    "Breakout": detect_breakout,
    "Breakdown": detect_breakdown,
    "Bullish Doji": detect_bullish_doji,
    "Bearish Doji": detect_bearish_doji,
    "Hammer": detect_hammer,
    "Hanging Man": detect_hanging_man,
    "Inverted Hammer": detect_inverted_hammer,
    "Shooting Star": detect_shooting_star,
    "Bullish Engulfing": detect_bullish_engulfing,
    "Bearish Engulfing": detect_bearish_engulfing,
    "Morning Star": detect_morning_star,
    "Evening Star": detect_evening_star,
    "Dark Cloud Cover": detect_dark_cloud_cover,
    "Piercing Line": detect_piercing_line,
}

__all__ = [
    "PatternMatch",
    "DETECTORS",
    "detect_double_bottom",
    "detect_double_top",
    "detect_cup_and_handle",
    "detect_head_and_shoulders",
    "detect_inverse_head_and_shoulders",
    "detect_bull_flag",
    "detect_bear_flag",
    "detect_ascending_triangle",
    "detect_descending_triangle",
    "detect_falling_wedge",
    "detect_rising_wedge",
    "detect_breakout",
    "detect_breakdown",
    "detect_bullish_doji",
    "detect_bearish_doji",
    "detect_hammer",
    "detect_hanging_man",
    "detect_inverted_hammer",
    "detect_shooting_star",
    "detect_bullish_engulfing",
    "detect_bearish_engulfing",
    "detect_morning_star",
    "detect_evening_star",
    "detect_dark_cloud_cover",
    "detect_piercing_line",
]
