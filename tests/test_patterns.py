"""Teste chaque détecteur de `engine/patterns/` sur une série de prix
synthétique construite pour suivre exactement sa géométrie attendue.

Ces tests ne nécessitent ni base de données ni Docker : ils travaillent
uniquement sur des `DataFrame` pandas construits en mémoire.
"""

import numpy as np
import pandas as pd
import pytest

from engine.patterns import (
    detect_ascending_triangle,
    detect_bear_flag,
    detect_breakdown,
    detect_breakout,
    detect_bull_flag,
    detect_cup_and_handle,
    detect_descending_triangle,
    detect_double_bottom,
    detect_double_top,
    detect_falling_wedge,
    detect_head_and_shoulders,
    detect_inverse_head_and_shoulders,
    detect_rising_wedge,
)
from engine.detect import DETECTORS, detect_all


def ramp(start: float, end: float, n: int) -> list[float]:
    return list(np.linspace(start, end, n))


def path(*segments: list[float]) -> list[float]:
    """Concatène des segments en supprimant le premier point de chaque
    segment après le premier (identique au dernier point du précédent) —
    évite les paliers de deux points égaux consécutifs qui empêcheraient
    `scipy.signal.argrelextrema` de reconnaître un extremum strict."""
    result = list(segments[0])
    for seg in segments[1:]:
        result.extend(seg[1:])
    return result


def make_df(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    n = len(closes)
    idx = pd.bdate_range(start="2023-01-02", periods=n)
    close = pd.Series(closes, index=idx, dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.002
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.998
    volume = pd.Series(volumes if volumes is not None else [1_000_000] * n, index=idx, dtype="int64")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def assert_single_confident_match(matches, pattern_type: str):
    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_type == pattern_type
    assert 0.0 <= match.confidence <= 100.0


class TestDoubleBottom:
    def test_detects_confirmed_double_bottom(self):
        closes = path(ramp(100, 90, 7), ramp(90, 100, 9), ramp(100, 90.5, 9), ramp(90.5, 103, 9))
        matches = detect_double_bottom(make_df(closes))
        assert_single_confident_match(matches, "Double Bottom")

    def test_no_match_without_breakout_confirmation(self):
        # Même géométrie, mais la dernière clôture ne dépasse pas la résistance.
        closes = path(ramp(100, 90, 7), ramp(90, 100, 9), ramp(100, 90.5, 9), ramp(90.5, 95, 9))
        assert detect_double_bottom(make_df(closes)) == []


class TestDoubleTop:
    def test_detects_confirmed_double_top(self):
        closes = path(ramp(100, 110, 7), ramp(110, 100, 9), ramp(100, 109.5, 9), ramp(109.5, 97, 9))
        matches = detect_double_top(make_df(closes))
        assert_single_confident_match(matches, "Double Top")


class TestHeadAndShoulders:
    def test_detects_confirmed_head_and_shoulders(self):
        closes = path(
            ramp(90, 100, 7),
            ramp(100, 92, 7),
            ramp(92, 115, 7),
            ramp(115, 92.3, 7),
            ramp(92.3, 99.5, 7),
            ramp(99.5, 88, 7),
        )
        matches = detect_head_and_shoulders(make_df(closes))
        assert_single_confident_match(matches, "Head & Shoulders")


class TestInverseHeadAndShoulders:
    def test_detects_confirmed_inverse_head_and_shoulders(self):
        closes = path(
            ramp(110, 100, 7),
            ramp(100, 108, 7),
            ramp(108, 85, 7),
            ramp(85, 108.3, 7),
            ramp(108.3, 100.5, 7),
            ramp(100.5, 113, 7),
        )
        matches = detect_inverse_head_and_shoulders(make_df(closes))
        assert_single_confident_match(matches, "Inverse Head & Shoulders")


class TestCupAndHandle:
    def test_detects_confirmed_cup_and_handle(self):
        closes = path(
            ramp(90, 100, 7),  # rebord gauche
            ramp(100, 85, 10),  # fond de la coupe
            ramp(85, 100.5, 10),  # rebord droit
            ramp(100.5, 97, 5),  # anse
            ramp(97, 103, 5),  # cassure
        )
        matches = detect_cup_and_handle(make_df(closes))
        assert_single_confident_match(matches, "Cup & Handle")


class TestAscendingTriangle:
    def test_detects_confirmed_ascending_triangle(self):
        closes = path(
            ramp(95, 100, 5),
            ramp(100, 96, 5),
            ramp(96, 100.2, 5),
            ramp(100.2, 97.5, 5),
            ramp(97.5, 100.1, 5),
            ramp(100.1, 99, 5),
            ramp(99, 103, 5),
        )
        matches = detect_ascending_triangle(make_df(closes))
        assert_single_confident_match(matches, "Ascending Triangle")


class TestDescendingTriangle:
    def test_detects_confirmed_descending_triangle(self):
        closes = path(
            ramp(105, 100, 5),
            ramp(100, 104, 5),
            ramp(104, 99.8, 5),
            ramp(99.8, 102.5, 5),
            ramp(102.5, 100.1, 5),
            ramp(100.1, 101, 5),
            ramp(101, 97, 5),
        )
        matches = detect_descending_triangle(make_df(closes))
        assert_single_confident_match(matches, "Descending Triangle")


class TestFallingWedge:
    def test_detects_confirmed_falling_wedge(self):
        closes = path(
            ramp(105, 110, 4),
            ramp(110, 100, 5),
            ramp(100, 106, 5),
            ramp(106, 98, 5),
            ramp(98, 102, 5),
            ramp(102, 97, 5),
            ramp(97, 108, 6),
        )
        matches = detect_falling_wedge(make_df(closes))
        assert_single_confident_match(matches, "Falling Wedge")


class TestRisingWedge:
    def test_detects_confirmed_rising_wedge(self):
        closes = path(
            ramp(97, 100, 4),
            ramp(100, 90, 5),
            ramp(90, 104, 5),
            ramp(104, 96, 5),
            ramp(96, 106, 5),
            ramp(106, 101, 5),
            ramp(101, 90, 6),
        )
        matches = detect_rising_wedge(make_df(closes))
        assert_single_confident_match(matches, "Rising Wedge")


class TestBullFlag:
    def test_detects_confirmed_bull_flag(self):
        closes = path(ramp(100, 112, 10), ramp(112, 108, 15)) + [115]
        matches = detect_bull_flag(make_df(closes))
        assert_single_confident_match(matches, "Bull Flag")

    def test_no_match_without_pole(self):
        # Pas de mât : simple bruit sans mouvement impulsif.
        closes = path(ramp(100, 101, 10), ramp(101, 100, 15)) + [100.5]
        assert detect_bull_flag(make_df(closes)) == []


class TestBearFlag:
    def test_detects_confirmed_bear_flag(self):
        closes = path(ramp(112, 100, 10), ramp(101, 104, 14)) + [95]
        matches = detect_bear_flag(make_df(closes))
        assert_single_confident_match(matches, "Bear Flag")


class TestBreakout:
    def test_detects_confirmed_breakout(self):
        closes = [
            95, 96, 97, 98, 99, 100, 98, 96, 94, 96,
            98, 99, 100, 98, 96, 94, 97, 99, 98, 105,
        ]
        matches = detect_breakout(make_df(closes))
        assert_single_confident_match(matches, "Breakout")

    def test_no_match_on_continuous_uptrend(self):
        # Grimpée continue : pas de repli avant le dernier plus haut -> pas
        # un vrai "palier puis cassure".
        closes = ramp(100, 150, 20)
        assert detect_breakout(make_df(closes)) == []


class TestBreakdown:
    def test_detects_confirmed_breakdown(self):
        closes = [
            105, 104, 103, 102, 101, 100, 102, 104, 106, 104,
            102, 101, 100, 102, 104, 106, 103, 101, 102, 95,
        ]
        matches = detect_breakdown(make_df(closes))
        assert_single_confident_match(matches, "Breakdown")


def test_registry_matches_the_documented_patterns():
    # 13 figures chartistes (Phase 1) + 12 figures en bougies japonaises
    # (ad hoc, voir George_AnalyseTechnique_Kabbaj_Synthese.md) + 35 figures/
    # concepts supplémentaires (ad hoc, voir
    # George_Strategies_Images_Synthese.md).
    assert len(DETECTORS) == 60


def test_detect_all_finds_nothing_on_a_smooth_monotonic_trend():
    # Une tendance strictement monotone n'a pas d'extrema locaux : aucune
    # figure de retournement/continuation ne peut s'y former par construction.
    df = make_df(ramp(100, 130, 60))
    matches = detect_all(df)
    assert matches == []


def test_detect_all_raises_on_missing_columns():
    df = make_df(ramp(100, 110, 20)).drop(columns=["volume"])
    with pytest.raises(ValueError):
        detect_all(df)
