"""Teste `engine/exit_levels.py` sur les 25 types de figures (13 chartistes +
12 bougies japonaises), en réutilisant les séries synthétiques et le
détecteur réel de `tests/test_patterns.py`/`tests/test_candlestick.py`
plutôt que des `context` reconstruits à la main — la même figure sert à
vérifier la détection (Phase 1) et les niveaux de sortie qui en découlent
(Phase 6), garantissant que les deux restent cohérents."""
import pytest

from engine.exit_levels import (
    CANDLESTICK_RISK_REWARD_RATIO,
    bollinger_band_levels,
    fibonacci_retracement_levels,
    is_bullish,
    propose_levels,
)
from engine.patterns import DETECTORS
from tests.test_candlestick import DOWNTREND, UPTREND, _candle_df
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
    "Bullish Doji": (
        lambda: _candle_df(DOWNTREND, [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.05}]),
        True,
    ),
    "Bearish Doji": (
        lambda: _candle_df(UPTREND, [{"open": 120.0, "high": 121.0, "low": 119.0, "close": 119.95}]),
        False,
    ),
    "Hammer": (
        lambda: _candle_df(DOWNTREND, [{"open": 99.8, "high": 100.5, "low": 96.0, "close": 100.2}]),
        True,
    ),
    "Hanging Man": (
        lambda: _candle_df(UPTREND, [{"open": 119.8, "high": 120.5, "low": 116.0, "close": 120.2}]),
        False,
    ),
    "Inverted Hammer": (
        lambda: _candle_df(DOWNTREND, [{"open": 99.8, "high": 104.0, "low": 99.6, "close": 100.0}]),
        True,
    ),
    "Shooting Star": (
        lambda: _candle_df(UPTREND, [{"open": 119.8, "high": 124.0, "low": 119.6, "close": 120.0}]),
        False,
    ),
    "Bullish Engulfing": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 101.0, "high": 101.2, "low": 98.8, "close": 99.0},
                {"open": 98.5, "high": 101.7, "low": 98.3, "close": 101.5},
            ],
        ),
        True,
    ),
    "Bearish Engulfing": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 119.0, "high": 121.2, "low": 118.8, "close": 121.0},
                {"open": 121.5, "high": 121.7, "low": 118.3, "close": 118.5},
            ],
        ),
        False,
    ),
    "Morning Star": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 98.0, "high": 98.4, "low": 97.7, "close": 98.2},
                {"open": 98.5, "high": 103.2, "low": 98.3, "close": 103.0},
            ],
        ),
        True,
    ),
    "Evening Star": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 115.0, "high": 120.2, "low": 114.8, "close": 120.0},
                {"open": 122.0, "high": 122.3, "low": 121.6, "close": 121.8},
                {"open": 121.5, "high": 121.7, "low": 116.8, "close": 117.0},
            ],
        ),
        False,
    ),
    "Dark Cloud Cover": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 100.0, "high": 105.2, "low": 99.8, "close": 105.0},
                {"open": 106.0, "high": 106.2, "low": 100.8, "close": 101.0},
            ],
        ),
        False,
    ),
    "Piercing Line": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 99.0, "high": 104.2, "low": 98.8, "close": 104.0},
            ],
        ),
        True,
    ),
}


def test_all_pattern_types_are_covered():
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


def test_fibonacci_retracement_levels_are_ordered_between_swing_points():
    levels = fibonacci_retracement_levels(swing_low=90.0, swing_high=110.0)
    assert set(levels) == {"38.2%", "50.0%", "61.8%", "76.4%"}
    # Chaque niveau doit se trouver strictement entre le creux et le sommet,
    # et plus le ratio est élevé, plus le niveau est proche du creux.
    assert 90.0 < levels["76.4%"] < levels["61.8%"] < levels["50.0%"] < levels["38.2%"] < 110.0


def test_bollinger_band_levels_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert bollinger_band_levels(df, 5) is None


def test_bollinger_band_levels_are_ordered_around_the_median():
    df = make_df(ramp(100, 130, 30))
    levels = bollinger_band_levels(df, len(df) - 1)
    assert levels is not None
    assert set(levels) == {"bande_basse", "bande_mediane", "bande_haute"}
    assert levels["bande_basse"] < levels["bande_mediane"] < levels["bande_haute"]


@pytest.mark.parametrize("pattern_type", sorted(CASES))
def test_candlestick_levels_respect_minimum_risk_reward_ratio(pattern_type):
    """Les 12 figures en bougies utilisent `_candlestick_levels`, dont le
    take-profit est explicitement dérivé du ratio risque/rendement minimal
    documenté par Kabbaj (2011, §5 de la synthèse) — vérifié ici pour
    confirmer qu'aucun changement futur ne le fait dériver silencieusement."""
    if pattern_type not in {
        "Bullish Doji", "Bearish Doji", "Hammer", "Hanging Man", "Inverted Hammer", "Shooting Star",
        "Bullish Engulfing", "Bearish Engulfing", "Morning Star", "Evening Star", "Dark Cloud Cover", "Piercing Line",
    }:
        pytest.skip("figure chartiste classique, pas une bougie — pas de ratio risque/rendement fixe")

    make_series, bullish = CASES[pattern_type]
    df = make_series()
    match = DETECTORS[pattern_type](df)[0]
    entry_price = float(df["close"].iloc[-1])

    take_profit, stop_loss = propose_levels(pattern_type, match.context, entry_price, df)
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    assert reward == pytest.approx(risk * CANDLESTICK_RISK_REWARD_RATIO, rel=1e-6)
