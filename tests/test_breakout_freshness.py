"""Une figure n'est retenue que si sa cassure est récente
(`engine/patterns/common.py:is_fresh_breakout`) : "la dernière clôture est
au-delà du niveau" reste vrai des années après la cassure, ce qui a produit en
production une proposition sur ATO.PA avec un double sommet de 2024 (stop à
179,56 € pour une entrée à 31,80 €). Séries synthétiques, sans DB ni réseau.
"""

import pytest

from engine.patterns import DETECTORS
from engine.patterns.common import BREAKOUT_FRESHNESS_BARS, is_fresh_breakout
from tests.test_patterns import make_df, path, ramp

# Pour chaque figure : la géométrie jusqu'au dernier pivot, le niveau à casser,
# le sens, et une clôture au-delà de ce niveau.
CASES = {
    "Double Bottom": (path(ramp(100, 90, 7), ramp(90, 100, 9), ramp(100, 90.5, 9), ramp(90.5, 99, 6)), 100, True, 103),
    "Double Top": (path(ramp(100, 110, 7), ramp(110, 100, 9), ramp(100, 109.5, 9), ramp(109.5, 101, 6)), 100, False, 97),
    "Head & Shoulders": (
        path(ramp(90, 100, 7), ramp(100, 92, 7), ramp(92, 115, 7), ramp(115, 92.3, 7), ramp(92.3, 99.5, 7), ramp(99.5, 94, 5)),
        92.15, False, 88,
    ),
    "Inverse Head & Shoulders": (
        path(ramp(110, 100, 7), ramp(100, 108, 7), ramp(108, 85, 7), ramp(85, 108.3, 7), ramp(108.3, 100.5, 7), ramp(100.5, 106, 5)),
        108.15, True, 113,
    ),
    "Cup & Handle": (
        path(ramp(90, 100, 7), ramp(100, 85, 10), ramp(85, 100.5, 10), ramp(100.5, 97, 5), ramp(97, 100, 4)),
        100.5, True, 103,
    ),
    "Triple Top": (
        path(ramp(100, 110, 7), ramp(110, 102, 7), ramp(102, 110.2, 7), ramp(110.2, 101, 7), ramp(101, 109.8, 7), ramp(109.8, 103, 5)),
        101, False, 95,
    ),
    "Triple Bottom": (
        path(ramp(100, 90, 7), ramp(90, 98, 7), ramp(98, 90.2, 7), ramp(90.2, 99, 7), ramp(99, 90.8, 7), ramp(90.8, 97, 5)),
        99, True, 105,
    ),
    "Bullish Break of Structure": (path(ramp(100, 110, 7), ramp(110, 95, 10), ramp(95, 108, 5)), 110, True, 112),
    "Bearish Break of Structure": (path(ramp(100, 90, 7), ramp(90, 105, 10), ramp(105, 92, 5)), 90, False, 88),
}


def _beyond(price: float, bullish: bool, n: int) -> list[float]:
    """`n` clôtures au-delà du niveau, qui s'en éloignent régulièrement (aucun
    nouvel extremum local, donc la même figure reste la seule candidate)."""
    step = 0.1 if bullish else -0.1
    return [price + step * i for i in range(n)]


@pytest.mark.parametrize("pattern_type", sorted(CASES))
@pytest.mark.parametrize("bars", [1, BREAKOUT_FRESHNESS_BARS])
def test_recent_breakout_is_detected(pattern_type, bars):
    base, _, bullish, broken = CASES[pattern_type]
    matches = DETECTORS[pattern_type](make_df(base + _beyond(broken, bullish, bars)))
    assert [m.pattern_type for m in matches] == [pattern_type]


@pytest.mark.parametrize("pattern_type", sorted(CASES))
@pytest.mark.parametrize("bars", [BREAKOUT_FRESHNESS_BARS + 1, 60])
def test_old_breakout_is_ignored(pattern_type, bars):
    base, _, bullish, broken = CASES[pattern_type]
    assert DETECTORS[pattern_type](make_df(base + _beyond(broken, bullish, bars))) == []


@pytest.mark.parametrize("pattern_type", sorted(CASES))
def test_second_crossing_after_an_old_breakout_is_ignored(pattern_type):
    base, level, bullish, broken = CASES[pattern_type]
    came_back = base[-1]
    series = base + _beyond(broken, bullish, 8) + [came_back] * 8 + [broken]
    assert DETECTORS[pattern_type](make_df(series)) == []


def test_level_never_crossed_before_stays_eligible_however_old_the_pivot():
    closes = [100.0] + [101.0] * 500 + [97.0]
    assert is_fresh_breakout(closes, last_pivot_idx=0, level=100.0, bullish=False)


def test_close_within_the_buffer_does_not_count_as_a_crossing():
    closes = [101.0, 99.9, 101.0, 101.0, 101.0, 101.0, 101.0, 97.0]
    assert is_fresh_breakout(closes, last_pivot_idx=0, level=100.0, bullish=False)
