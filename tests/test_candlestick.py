"""Teste chaque détecteur de `engine/patterns/candlestick.py` sur une série
construite pour suivre exactement sa géométrie attendue — même discipline que
`tests/test_patterns.py` (séries construites à la main, pas aléatoires).

Contrairement aux 13 figures chartistes, une bougie a besoin d'un contrôle
OHLC précis (mèches, pas seulement le prix de clôture) : `_candle_df` combine
une tendance de fond construite comme `test_patterns.make_df` (mèches
serrées, non significatives) avec des bougies de signal aux OHLC explicites.
"""

import pandas as pd
import pytest

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
from tests.test_patterns import ramp


def _candle_df(trend_closes: list[float], signal_candles: list[dict]) -> pd.DataFrame:
    """`trend_closes` construit le contexte de tendance (mêmes mèches serrées
    que `test_patterns.make_df`) ; `signal_candles` est une liste de dicts
    `{"open", "high", "low", "close"}` (volume optionnel) ajoutés tels quels
    à la suite, pour contrôler précisément la géométrie de la ou des bougies
    de signal."""
    n = len(trend_closes)
    close = pd.Series(trend_closes, dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.002
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.998
    trend_df = pd.DataFrame(
        {
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
            "volume": [1_000_000] * n,
        }
    )
    signal_rows = []
    for candle in signal_candles:
        row = dict(candle)
        row.setdefault("volume", 1_000_000)
        signal_rows.append(row)
    full = pd.concat([trend_df, pd.DataFrame(signal_rows)], ignore_index=True)
    full.index = pd.bdate_range(start="2023-01-02", periods=len(full))
    return full


def assert_single_confident_match(matches, pattern_type: str):
    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_type == pattern_type
    assert 0.0 <= match.confidence <= 100.0


DOWNTREND = ramp(120, 100, 13)
UPTREND = ramp(100, 120, 13)


class TestDoji:
    def test_bullish_doji_after_downtrend(self):
        df = _candle_df(DOWNTREND, [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.05}])
        assert_single_confident_match(detect_bullish_doji(df), "Bullish Doji")

    def test_bearish_doji_after_uptrend(self):
        df = _candle_df(UPTREND, [{"open": 120.0, "high": 121.0, "low": 119.0, "close": 119.95}])
        assert_single_confident_match(detect_bearish_doji(df), "Bearish Doji")

    def test_no_match_without_trend_confirmation(self):
        """Même géométrie de doji, mais après un marché plat : le livre
        insiste sur le fait qu'aucune figure de bougie seule n'est
        exploitable sans confirmation de tendance (voir la synthèse
        Kabbaj, §2.1/§6)."""
        flat = [100.0] * 13
        df = _candle_df(flat, [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.05}])
        assert detect_bullish_doji(df) == []
        assert detect_bearish_doji(df) == []


class TestHammerAndHangingMan:
    HAMMER_SHAPE = {"open": 99.8, "high": 100.5, "low": 96.0, "close": 100.2}

    def test_hammer_after_downtrend(self):
        df = _candle_df(DOWNTREND, [self.HAMMER_SHAPE])
        assert_single_confident_match(detect_hammer(df), "Hammer")

    def test_hanging_man_after_uptrend(self):
        df = _candle_df(UPTREND, [{"open": 119.8, "high": 120.5, "low": 116.0, "close": 120.2}])
        assert_single_confident_match(detect_hanging_man(df), "Hanging Man")

    def test_hammer_shape_after_uptrend_is_not_a_hammer(self):
        df = _candle_df(UPTREND, [{"open": 119.8, "high": 120.5, "low": 116.0, "close": 120.2}])
        assert detect_hammer(df) == []


class TestInvertedHammerAndShootingStar:
    def test_inverted_hammer_after_downtrend(self):
        df = _candle_df(DOWNTREND, [{"open": 99.8, "high": 104.0, "low": 99.6, "close": 100.0}])
        assert_single_confident_match(detect_inverted_hammer(df), "Inverted Hammer")

    def test_shooting_star_after_uptrend(self):
        df = _candle_df(UPTREND, [{"open": 119.8, "high": 124.0, "low": 119.6, "close": 120.0}])
        assert_single_confident_match(detect_shooting_star(df), "Shooting Star")


class TestEngulfing:
    def test_bullish_engulfing_after_downtrend(self):
        df = _candle_df(
            DOWNTREND,
            [
                {"open": 101.0, "high": 101.2, "low": 98.8, "close": 99.0},
                {"open": 98.5, "high": 101.7, "low": 98.3, "close": 101.5},
            ],
        )
        assert_single_confident_match(detect_bullish_engulfing(df), "Bullish Engulfing")

    def test_bearish_engulfing_after_uptrend(self):
        df = _candle_df(
            UPTREND,
            [
                {"open": 119.0, "high": 121.2, "low": 118.8, "close": 121.0},
                {"open": 121.5, "high": 121.7, "low": 118.3, "close": 118.5},
            ],
        )
        assert_single_confident_match(detect_bearish_engulfing(df), "Bearish Engulfing")


class TestStars:
    def test_morning_star_after_downtrend(self):
        df = _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 98.0, "high": 98.4, "low": 97.7, "close": 98.2},
                {"open": 98.5, "high": 103.2, "low": 98.3, "close": 103.0},
            ],
        )
        assert_single_confident_match(detect_morning_star(df), "Morning Star")

    def test_evening_star_after_uptrend(self):
        df = _candle_df(
            UPTREND,
            [
                {"open": 115.0, "high": 120.2, "low": 114.8, "close": 120.0},
                {"open": 122.0, "high": 122.3, "low": 121.6, "close": 121.8},
                {"open": 121.5, "high": 121.7, "low": 116.8, "close": 117.0},
            ],
        )
        assert_single_confident_match(detect_evening_star(df), "Evening Star")


class TestCloudAndPiercing:
    def test_dark_cloud_cover_after_uptrend(self):
        df = _candle_df(
            UPTREND,
            [
                {"open": 100.0, "high": 105.2, "low": 99.8, "close": 105.0},
                {"open": 106.0, "high": 106.2, "low": 100.8, "close": 101.0},
            ],
        )
        assert_single_confident_match(detect_dark_cloud_cover(df), "Dark Cloud Cover")

    def test_piercing_line_after_downtrend(self):
        df = _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 99.0, "high": 104.2, "low": 98.8, "close": 104.0},
            ],
        )
        assert_single_confident_match(detect_piercing_line(df), "Piercing Line")
