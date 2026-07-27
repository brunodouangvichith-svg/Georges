"""Teste `engine/exit_levels.py` sur les 13 types de figures, en réutilisant
les séries synthétiques et le détecteur réel de `tests/test_patterns.py`
plutôt que des `context` reconstruits à la main — la même figure sert à
vérifier la détection (Phase 1) et les niveaux de sortie qui en découlent
(Phase 6), garantissant que les deux restent cohérents."""
import pytest

from engine.exit_levels import is_bullish, propose_levels
from engine.patterns import DETECTORS
from tests.test_patterns import make_df, path, ramp

CASES = {
    "Double Bottom": (
        lambda: make_df(path(ramp(100, 90, 7), ramp(90, 100, 9), ramp(100, 90.5, 9), ramp(90.5, 103, 9))),
        True,
    ),
    "Double Top": (
        lambda: make_df(path(ramp(100, 110, 7), ramp(110, 100, 9), ramp(100, 109.5, 9), ramp(109.5, 97, 9))),
        False,
    ),
    "Head & Shoulders": (
        lambda: make_df(
            path(
                ramp(90, 100, 7),
                ramp(100, 92, 7),
                ramp(92, 115, 7),
                ramp(115, 92.3, 7),
                ramp(92.3, 99.5, 7),
                ramp(99.5, 88, 7),
            )
        ),
        False,
    ),
    "Inverse Head & Shoulders": (
        lambda: make_df(
            path(
                ramp(110, 100, 7),
                ramp(100, 108, 7),
                ramp(108, 85, 7),
                ramp(85, 108.3, 7),
                ramp(108.3, 100.5, 7),
                ramp(100.5, 113, 7),
            )
        ),
        True,
    ),
    "Cup & Handle": (
        lambda: make_df(
            path(
                ramp(90, 100, 7),
                ramp(100, 85, 10),
                ramp(85, 100.5, 10),
                ramp(100.5, 97, 5),
                ramp(97, 103, 5),
            )
        ),
        True,
    ),
    "Ascending Triangle": (
        lambda: make_df(
            path(
                ramp(95, 100, 5),
                ramp(100, 96, 5),
                ramp(96, 100.2, 5),
                ramp(100.2, 97.5, 5),
                ramp(97.5, 100.1, 5),
                ramp(100.1, 99, 5),
                ramp(99, 103, 5),
            )
        ),
        True,
    ),
    "Descending Triangle": (
        lambda: make_df(
            path(
                ramp(105, 100, 5),
                ramp(100, 104, 5),
                ramp(104, 99.8, 5),
                ramp(99.8, 102.5, 5),
                ramp(102.5, 100.1, 5),
                ramp(100.1, 101, 5),
                ramp(101, 97, 5),
            )
        ),
        False,
    ),
    "Falling Wedge": (
        lambda: make_df(
            path(
                ramp(105, 110, 4),
                ramp(110, 100, 5),
                ramp(100, 106, 5),
                ramp(106, 98, 5),
                ramp(98, 102, 5),
                ramp(102, 97, 5),
                ramp(97, 108, 6),
            )
        ),
        True,
    ),
    "Rising Wedge": (
        lambda: make_df(
            path(
                ramp(97, 100, 4),
                ramp(100, 90, 5),
                ramp(90, 104, 5),
                ramp(104, 96, 5),
                ramp(96, 106, 5),
                ramp(106, 101, 5),
                ramp(101, 90, 6),
            )
        ),
        False,
    ),
    "Bull Flag": (lambda: make_df(path(ramp(100, 112, 10), ramp(112, 108, 15)) + [115]), True),
    "Bear Flag": (lambda: make_df(path(ramp(112, 100, 10), ramp(101, 104, 14)) + [95]), False),
    "Breakout": (
        lambda: make_df([95, 96, 97, 98, 99, 100, 98, 96, 94, 96, 98, 99, 100, 98, 96, 94, 97, 99, 98, 105]),
        True,
    ),
    "Breakdown": (
        lambda: make_df([105, 104, 103, 102, 101, 100, 102, 104, 106, 104, 102, 101, 100, 102, 104, 106, 103, 101, 102, 95]),
        False,
    ),
}


def test_all_thirteen_detectors_are_covered():
    assert set(CASES) == set(DETECTORS)


@pytest.mark.parametrize("pattern_type", sorted(CASES))
def test_is_bullish_matches_expected_direction(pattern_type):
    make_series, expected_bullish = CASES[pattern_type]
    assert is_bullish(pattern_type) == expected_bullish


@pytest.mark.parametrize("pattern_type", sorted(CASES))
def test_propose_levels_respects_direction(pattern_type):
    make_series, bullish = CASES[pattern_type]
    df = make_series()
    match = DETECTORS[pattern_type](df)[0]
    entry_price = float(df["close"].iloc[-1])

    take_profit, stop_loss = propose_levels(pattern_type, match.context, entry_price, df)

    if bullish:
        assert stop_loss < entry_price < take_profit
    else:
        assert take_profit < entry_price < stop_loss


def test_propose_levels_raises_on_unknown_pattern():
    with pytest.raises(KeyError):
        propose_levels("Pattern Inexistant", {}, 100.0, make_df(ramp(100, 110, 20)))
