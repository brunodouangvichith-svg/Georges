from engine.patterns.breakout import detect_breakdown, detect_breakout
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

# Registre des 13 détecteurs, chacun testable indépendamment (voir
# tests/test_patterns.py) et appelé par `engine.detect.detect_all`.
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
]
