"""Teste `engine/exit_levels.py` sur les 60 types de figures (13 chartistes +
12 bougies japonaises + 35 ajoutées via George_Strategies_Images_Synthese.md),
en réutilisant les séries synthétiques et le détecteur réel de
`tests/test_patterns.py`/`tests/test_candlestick.py`/les modules `*_extended`/
`test_crossover.py`/`test_smart_money.py` plutôt que des `context` reconstruits
à la main — la même figure sert à vérifier la détection (Phase 1) et les
niveaux de sortie qui en découlent (Phase 6), garantissant que les deux
restent cohérents. C'est précisément ce test qui a valeur de garde-fou pour
l'intégration : chaque détecteur écrit son `context` de son côté, chaque
formule de niveaux dans `engine/exit_levels.py` lit ce `context` de son
côté — sans ce test bout-en-bout, une clé mal orthographiée entre les deux
ne serait jamais détectée avant une vraie exécution en production."""
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
from tests.test_crossover import _closes_up_to_crossover, _DOWN_CLOSES, _UP_CLOSES
from tests.test_patterns import make_df, path, ramp
from tests.test_reversal_extended import _diamond_pattern_closes
from tests.test_smart_money import _append_gap_bar, _ohlc_df

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
    # --- George_Strategies_Images_Synthese.md -- figures chartistes classiques ---
    "Triple Top": (
        lambda: make_df(
            path(
                ramp(100, 110, 7), ramp(110, 102, 7), ramp(102, 110.2, 7),
                ramp(110.2, 101, 7), ramp(101, 109.8, 7), ramp(109.8, 95, 7),
            )
        ),
        False,
    ),
    "Triple Bottom": (
        lambda: make_df(
            path(
                ramp(100, 90, 7), ramp(90, 98, 7), ramp(98, 90.2, 7),
                ramp(90.2, 99, 7), ramp(99, 90.8, 7), ramp(90.8, 105, 7),
            )
        ),
        True,
    ),
    "Rounding Top": (
        lambda: make_df([-0.1 * (x - 10) ** 2 + 105 for x in range(30)]),
        False,
    ),
    "Rounding Bottom": (
        lambda: make_df([0.1 * (x - 10) ** 2 + 95 for x in range(30)]),
        True,
    ),
    "Diamond Top": (
        lambda: make_df(
            ramp(85, 100, 10) + _diamond_pattern_closes(14, 15, base=100, start_amp=1, peak_amp=15) + [70]
        ),
        False,
    ),
    "Diamond Bottom": (
        lambda: make_df(
            ramp(100, 85, 10) + _diamond_pattern_closes(14, 15, base=100, start_amp=1, peak_amp=15) + [130]
        ),
        True,
    ),
    "Symmetrical Triangle Bullish": (
        lambda: make_df(
            path(
                ramp(90, 112, 5), ramp(112, 96, 5), ramp(96, 107, 5), ramp(107, 99, 5),
                ramp(99, 103, 5), ramp(103, 100.5, 5), ramp(100.5, 118, 6),
            )
        ),
        True,
    ),
    "Symmetrical Triangle Bearish": (
        lambda: make_df(
            path(
                ramp(90, 112, 5), ramp(112, 96, 5), ramp(96, 107, 5), ramp(107, 99, 5),
                ramp(99, 103, 5), ramp(103, 100.5, 5), ramp(100.5, 85, 6),
            )
        ),
        False,
    ),
    "Rectangle Bullish": (
        lambda: make_df(
            path(
                ramp(100, 105, 5), ramp(105, 95, 5), ramp(95, 104.5, 5), ramp(104.5, 95.5, 5),
                ramp(95.5, 105.2, 5), ramp(105.2, 96, 5), ramp(96, 112, 6),
            )
        ),
        True,
    ),
    "Rectangle Bearish": (
        lambda: make_df(
            path(
                ramp(100, 105, 5), ramp(105, 95, 5), ramp(95, 104.5, 5), ramp(104.5, 95.5, 5),
                ramp(95.5, 105.2, 5), ramp(105.2, 96, 5), ramp(96, 88, 6),
            )
        ),
        False,
    ),
    "Bull Pennant": (
        lambda: make_df(
            path(
                ramp(100, 130, 9), ramp(130, 121, 4), ramp(121, 128, 4), ramp(128, 123, 4),
                ramp(123, 126.5, 4), ramp(126.5, 125, 3), ramp(125, 140, 2),
            )
        ),
        True,
    ),
    "Bear Pennant": (
        lambda: make_df(
            path(
                ramp(130, 100, 9), ramp(100, 109, 4), ramp(109, 102, 4), ramp(102, 107, 4),
                ramp(107, 103.5, 4), ramp(103.5, 105, 3), ramp(105, 90, 2),
            )
        ),
        False,
    ),
    # --- George_Strategies_Images_Synthese.md -- bougies japonaises supplémentaires ---
    "Bullish Harami": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 100.0, "high": 100.2, "low": 94.0, "close": 94.5},
                {"open": 96.0, "high": 97.3, "low": 95.8, "close": 97.0},
            ],
        ),
        True,
    ),
    "Bearish Harami": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 120.0, "high": 126.0, "low": 119.8, "close": 125.5},
                {"open": 124.0, "high": 124.3, "low": 122.7, "close": 123.0},
            ],
        ),
        False,
    ),
    "Three White Soldiers": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 100.0, "high": 103.3, "low": 99.8, "close": 103.0},
                {"open": 101.5, "high": 105.8, "low": 101.3, "close": 105.5},
                {"open": 104.0, "high": 108.3, "low": 103.8, "close": 108.0},
            ],
        ),
        True,
    ),
    "Three Black Crows": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 120.0, "high": 120.2, "low": 116.7, "close": 117.0},
                {"open": 118.5, "high": 118.7, "low": 114.2, "close": 114.5},
                {"open": 116.0, "high": 116.2, "low": 111.2, "close": 111.5},
            ],
        ),
        False,
    ),
    "Bullish Kicker": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 106.5, "high": 110.3, "low": 106.0, "close": 110.0},
            ],
        ),
        True,
    ),
    "Bearish Kicker": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 100.0, "high": 105.2, "low": 99.8, "close": 105.0},
                {"open": 98.5, "high": 99.0, "low": 94.7, "close": 95.0},
            ],
        ),
        False,
    ),
    "Dragonfly Doji": (
        lambda: _candle_df(DOWNTREND, [{"open": 99.9, "high": 100.0, "low": 90.0, "close": 100.0}]),
        True,
    ),
    "Bullish Marubozu": (
        lambda: _candle_df(DOWNTREND, [{"open": 100.1, "high": 110.0, "low": 100.0, "close": 109.9}]),
        True,
    ),
    "Bearish Marubozu": (
        lambda: _candle_df(UPTREND, [{"open": 109.9, "high": 110.0, "low": 100.0, "close": 100.1}]),
        False,
    ),
    "Bullish Inside Bar": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 100.0, "high": 110.0, "low": 95.0, "close": 102.0},
                {"open": 102.0, "high": 105.0, "low": 100.0, "close": 103.0},
                {"open": 104.0, "high": 107.2, "low": 103.8, "close": 107.0},
            ],
        ),
        True,
    ),
    "Bearish Inside Bar": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 100.0, "high": 110.0, "low": 95.0, "close": 102.0},
                {"open": 102.0, "high": 105.0, "low": 100.0, "close": 103.0},
                {"open": 101.0, "high": 101.5, "low": 97.5, "close": 98.0},
            ],
        ),
        False,
    ),
    "Bullish Outside Bar": (
        lambda: _candle_df(
            DOWNTREND,
            [
                {"open": 101.0, "high": 105.0, "low": 100.0, "close": 102.0},
                {"open": 98.0, "high": 108.0, "low": 97.0, "close": 107.0},
            ],
        ),
        True,
    ),
    "Bearish Outside Bar": (
        lambda: _candle_df(
            UPTREND,
            [
                {"open": 101.0, "high": 105.0, "low": 100.0, "close": 102.0},
                {"open": 106.0, "high": 108.0, "low": 97.0, "close": 98.0},
            ],
        ),
        False,
    ),
    # --- George_Strategies_Images_Synthese.md -- Golden Cross / Death Cross ---
    "Golden Cross": (
        lambda: make_df(_closes_up_to_crossover(_UP_CLOSES, bullish=True)),
        True,
    ),
    "Death Cross": (
        lambda: make_df(_closes_up_to_crossover(_DOWN_CLOSES, bullish=False)),
        False,
    ),
    # --- George_Strategies_Images_Synthese.md -- Smart Money Concepts ---
    "Bullish Fair Value Gap": (
        lambda: make_df([100, 101, 110, 130]),
        True,
    ),
    "Bearish Fair Value Gap": (
        lambda: make_df([100, 99, 90, 70]),
        False,
    ),
    "Bullish Breakaway Gap": (
        lambda: _append_gap_bar(
            make_df(
                [95, 100, 96, 99, 95, 100, 97, 99, 96, 100, 95, 99, 96, 100, 97, 99, 95, 100, 97],
                volumes=[1_000_000] * 19,
            ),
            open_=112.0, high=115.0, low=111.0, close=113.0, volume=5_000_000,
        ),
        True,
    ),
    "Bearish Breakaway Gap": (
        lambda: _append_gap_bar(
            make_df(
                [105, 100, 104, 101, 105, 100, 103, 101, 104, 100, 105, 101, 104, 100, 103, 101, 105, 100, 103],
                volumes=[1_000_000] * 19,
            ),
            open_=88.0, high=89.0, low=85.0, close=87.0, volume=5_000_000,
        ),
        False,
    ),
    "Bullish Order Block": (
        lambda: make_df([100, 100.1, 100, 100.2, 100.1, 99, 103, 106, 109, 100]),
        True,
    ),
    "Bearish Order Block": (
        lambda: make_df([100, 99.9, 100, 99.8, 99.9, 101, 97, 94, 91, 100]),
        False,
    ),
    "Bullish Break of Structure": (
        lambda: make_df(path(ramp(100, 110, 7), ramp(110, 95, 10), ramp(95, 111, 5))),
        True,
    ),
    "Bearish Break of Structure": (
        lambda: make_df(path(ramp(100, 90, 7), ramp(90, 105, 10), ramp(105, 89, 5))),
        False,
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
        # George_Strategies_Images_Synthese.md -- mêmes formules à ratio fixe (_candlestick_levels-style),
        # contrairement à Harami/Three Soldiers-Crows/Inside-Outside Bar qui ont leur propre géométrie.
        "Bullish Kicker", "Bearish Kicker", "Dragonfly Doji", "Bullish Marubozu", "Bearish Marubozu",
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
