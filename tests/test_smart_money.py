"""Teste les 8 détecteurs "Smart Money Concepts" de
`engine/patterns/smart_money.py` : Fair Value Gap, Breakaway Gap, Order
Block, Break of Structure (variantes haussière/baissière de chacun).

Comme `tests/test_patterns.py`, ces tests travaillent uniquement sur des
`DataFrame` pandas construits en mémoire, sans base de données ni Docker.
"""

import pandas as pd

from engine.patterns.smart_money import (
    detect_bearish_break_of_structure,
    detect_bearish_breakaway_gap,
    detect_bearish_fair_value_gap,
    detect_bearish_order_block,
    detect_bullish_break_of_structure,
    detect_bullish_breakaway_gap,
    detect_bullish_fair_value_gap,
    detect_bullish_order_block,
)
from tests.test_patterns import make_df, path, ramp


def _ohlc_df(bars: list[tuple[float, float, float, float, float]]) -> pd.DataFrame:
    """Construit un DataFrame OHLCV à partir de bougies explicites
    (open, high, low, close, volume) — nécessaire pour le Breakaway Gap, qui
    exige un vrai gap de prix (le bas du jour au-dessus du haut de la
    veille). `make_df` de `tests.test_patterns` ne peut pas produire un tel
    gap : son `open` d'une bougie est toujours calé sur la `close` de la
    précédente, donc les bandes haut/bas de deux bougies consécutives se
    chevauchent toujours par construction, quelle que soit l'amplitude du
    mouvement — contrairement au FVG (non-chevauchement sur 3 bougies avec
    la bougie médiane "au milieu"), qui reste atteignable avec `make_df`."""
    n = len(bars)
    idx = pd.bdate_range(start="2023-01-02", periods=n)
    opens, highs, lows, closes, volumes = zip(*bars)
    return pd.DataFrame(
        {
            "open": pd.Series(opens, index=idx, dtype=float),
            "high": pd.Series(highs, index=idx, dtype=float),
            "low": pd.Series(lows, index=idx, dtype=float),
            "close": pd.Series(closes, index=idx, dtype=float),
            "volume": pd.Series(volumes, index=idx, dtype="int64"),
        }
    )


def _append_gap_bar(base: pd.DataFrame, open_: float, high: float, low: float, close: float, volume: float) -> pd.DataFrame:
    next_idx = pd.bdate_range(start=base.index[-1] + pd.tseries.offsets.BDay(1), periods=1)
    gap_row = pd.DataFrame(
        {"open": [open_], "high": [high], "low": [low], "close": [close], "volume": [volume]}, index=next_idx
    )
    return pd.concat([base, gap_row])


class TestBullishFairValueGap:
    def test_detects_freshly_formed_gap(self):
        # c-2 = 100/101 ; c-1 = 101->110 (haussière) ; c0 = 110->130 (haussière)
        # low(c0) = 110*0.998 = 109.78 > high(c-2) = 101*1.002 = 101.202 : gap net.
        closes = [100, 101, 110, 130]
        matches = detect_bullish_fair_value_gap(make_df(closes))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bullish Fair Value Gap"
        assert 0.0 <= matches[0].confidence <= 100.0
        assert matches[0].context["gap_top"] > matches[0].context["gap_bottom"]

    def test_no_match_with_too_few_bars(self):
        assert detect_bullish_fair_value_gap(make_df([100, 101])) == []


class TestBearishFairValueGap:
    def test_detects_freshly_formed_gap(self):
        closes = [100, 99, 90, 70]
        matches = detect_bearish_fair_value_gap(make_df(closes))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bearish Fair Value Gap"
        assert matches[0].context["gap_top"] > matches[0].context["gap_bottom"]

    def test_no_match_with_too_few_bars(self):
        assert detect_bearish_fair_value_gap(make_df([100, 99])) == []


class TestBullishBreakawayGap:
    _CONSOLIDATION = [95, 100, 96, 99, 95, 100, 97, 99, 96, 100, 95, 99, 96, 100, 97, 99, 95, 100, 97]

    def test_detects_gap_breakout_with_volume_confirmation(self):
        base = make_df(self._CONSOLIDATION, volumes=[1_000_000] * len(self._CONSOLIDATION))
        # Dernière bougie de consolidation : close=97, high ~= 100.2 -> le
        # gap doit ouvrir/creuser strictement au-dessus pour un vrai gap.
        df = _append_gap_bar(base, open_=112.0, high=115.0, low=111.0, close=113.0, volume=5_000_000)
        matches = detect_bullish_breakaway_gap(df)
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bullish Breakaway Gap"
        assert matches[0].context["resistance"] == 100.0
        assert matches[0].context["gap_top"] > matches[0].context["gap_bottom"]

    def test_no_match_without_a_real_price_gap(self):
        base = make_df(self._CONSOLIDATION, volumes=[1_000_000] * len(self._CONSOLIDATION))
        # Même cassure et même volume, mais le bas du jour chevauche le haut
        # de la veille : pas un vrai gap (ce serait au mieux un FVG).
        df = _append_gap_bar(base, open_=101.0, high=115.0, low=99.0, close=113.0, volume=5_000_000)
        assert detect_bullish_breakaway_gap(df) == []


class TestBearishBreakawayGap:
    _CONSOLIDATION = [105, 100, 104, 101, 105, 100, 103, 101, 104, 100, 105, 101, 104, 100, 103, 101, 105, 100, 103]

    def test_detects_gap_breakdown_with_volume_confirmation(self):
        base = make_df(self._CONSOLIDATION, volumes=[1_000_000] * len(self._CONSOLIDATION))
        df = _append_gap_bar(base, open_=88.0, high=89.0, low=85.0, close=87.0, volume=5_000_000)
        matches = detect_bearish_breakaway_gap(df)
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bearish Breakaway Gap"
        assert matches[0].context["support"] == 100.0
        assert matches[0].context["gap_top"] > matches[0].context["gap_bottom"]

    def test_no_match_without_enough_volume(self):
        base = make_df(self._CONSOLIDATION, volumes=[1_000_000] * len(self._CONSOLIDATION))
        # Même vrai gap, mais volume de la bougie de cassure au niveau de la
        # moyenne (pas 1.5x) : condition de volume du BAG non remplie.
        df = _append_gap_bar(base, open_=88.0, high=89.0, low=85.0, close=87.0, volume=1_000_000)
        assert detect_bearish_breakaway_gap(df) == []


class TestBullishOrderBlock:
    # i=5 : bougie baissière (100.1 -> 99) suivie d'une impulsion haussière
    # sur 3 bougies (99 -> 103 -> 106 -> 109, soit +10% > IMPULSE_MIN_RETURN)
    # puis un retour (bougie 9 : 109 -> 100) qui retest la zone [98.802;
    # 100.3] de la bougie 5 sans clôturer sous son bas.
    _RETEST_CLOSES = [100, 100.1, 100, 100.2, 100.1, 99, 103, 106, 109, 100]

    def test_detects_retest_of_the_order_block_zone(self):
        matches = detect_bullish_order_block(make_df(self._RETEST_CLOSES))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bullish Order Block"
        assert matches[0].context["ob_high"] > matches[0].context["ob_low"]

    def test_no_match_before_any_retest(self):
        # Même impulsion, mais le prix continue de grimper au lieu de
        # revenir tester la zone : pas encore de retest.
        closes = [100, 100.1, 100, 100.2, 100.1, 99, 103, 106, 109, 115]
        assert detect_bullish_order_block(make_df(closes)) == []


class TestBearishOrderBlock:
    # Symétrique (200 - x) du scénario haussier ci-dessus.
    _RETEST_CLOSES = [100, 99.9, 100, 99.8, 99.9, 101, 97, 94, 91, 100]

    def test_detects_retest_of_the_order_block_zone(self):
        matches = detect_bearish_order_block(make_df(self._RETEST_CLOSES))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bearish Order Block"
        assert matches[0].context["ob_high"] > matches[0].context["ob_low"]

    def test_no_match_with_too_few_bars(self):
        assert detect_bearish_order_block(make_df(ramp(100, 90, 4))) == []


class TestBullishBreakOfStructure:
    def _series(self, final_high: float) -> list[float]:
        return path(ramp(100, 110, 7), ramp(110, 95, 10), ramp(95, final_high, 5))

    def test_detects_close_breaking_above_prior_swing_high(self):
        matches = detect_bullish_break_of_structure(make_df(self._series(111)))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bullish Break of Structure"
        assert matches[0].context["swing_high"]["price"] == 110.0

    def test_no_match_without_breaking_the_swing_high(self):
        assert detect_bullish_break_of_structure(make_df(self._series(105))) == []


class TestBearishBreakOfStructure:
    def _series(self, final_low: float) -> list[float]:
        return path(ramp(100, 90, 7), ramp(90, 105, 10), ramp(105, final_low, 5))

    def test_detects_close_breaking_below_prior_swing_low(self):
        matches = detect_bearish_break_of_structure(make_df(self._series(89)))
        assert len(matches) == 1
        assert matches[0].pattern_type == "Bearish Break of Structure"
        assert matches[0].context["swing_low"]["price"] == 90.0

    def test_no_match_with_too_few_bars(self):
        assert detect_bearish_break_of_structure(make_df(ramp(100, 90, 5))) == []
