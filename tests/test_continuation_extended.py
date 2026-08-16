"""Teste les trois nouvelles familles de figures de continuation ajoutées à
`engine/patterns/continuation.py` : Symmetrical Triangle, Rectangle,
Bull/Bear Pennant. Même principe que `test_patterns.py` : des séries de prix
synthétiques construites pour suivre exactement la géométrie attendue par
chaque détecteur, sans base de données ni Docker.
"""

from engine.patterns.continuation import (
    detect_bear_pennant,
    detect_bull_pennant,
    detect_rectangle_bearish,
    detect_rectangle_bullish,
    detect_symmetrical_triangle_bearish,
    detect_symmetrical_triangle_bullish,
)
from tests.test_patterns import assert_single_confident_match, make_df, path, ramp


class TestSymmetricalTriangleBullish:
    def test_detects_confirmed_symmetrical_triangle_breakout(self):
        # Sommets décroissants (112 -> 107 -> 103) : résistance qui descend.
        # Creux croissants (96 -> 99 -> 100.5) : support qui monte.
        # Convergence nette, puis cassure franche au-dessus de la résistance.
        closes = path(
            ramp(90, 112, 5),
            ramp(112, 96, 5),
            ramp(96, 107, 5),
            ramp(107, 99, 5),
            ramp(99, 103, 5),
            ramp(103, 100.5, 5),
            ramp(100.5, 118, 6),
        )
        matches = detect_symmetrical_triangle_bullish(make_df(closes))
        assert_single_confident_match(matches, "Symmetrical Triangle Bullish")

    def test_no_match_before_enough_bars(self):
        closes = ramp(100, 105, 5)
        assert detect_symmetrical_triangle_bullish(make_df(closes)) == []

    def test_no_match_without_convergence(self):
        # Sommets et creux qui s'écartent au lieu de converger (canal qui
        # s'élargit) : pas un triangle symétrique malgré des pentes opposées.
        closes = path(
            ramp(90, 100, 5),
            ramp(100, 95, 5),
            ramp(95, 104, 5),
            ramp(104, 90, 5),
            ramp(90, 110, 5),
            ramp(110, 85, 5),
            ramp(85, 120, 6),
        )
        assert detect_symmetrical_triangle_bullish(make_df(closes)) == []


class TestSymmetricalTriangleBearish:
    def test_detects_confirmed_symmetrical_triangle_breakdown(self):
        # Même géométrie convergente que ci-dessus, mais cassure vers le bas.
        closes = path(
            ramp(90, 112, 5),
            ramp(112, 96, 5),
            ramp(96, 107, 5),
            ramp(107, 99, 5),
            ramp(99, 103, 5),
            ramp(103, 100.5, 5),
            ramp(100.5, 85, 6),
        )
        matches = detect_symmetrical_triangle_bearish(make_df(closes))
        assert_single_confident_match(matches, "Symmetrical Triangle Bearish")

    def test_no_match_before_enough_bars(self):
        closes = ramp(105, 100, 5)
        assert detect_symmetrical_triangle_bearish(make_df(closes)) == []


class TestRectangleBullish:
    def test_detects_confirmed_rectangle_breakout(self):
        # Range entre ~95 (support) et ~105 (résistance), testé plusieurs
        # fois de chaque côté, puis cassure franche au-dessus de 105.
        closes = path(
            ramp(100, 105, 5),
            ramp(105, 95, 5),
            ramp(95, 104.5, 5),
            ramp(104.5, 95.5, 5),
            ramp(95.5, 105.2, 5),
            ramp(105.2, 96, 5),
            ramp(96, 112, 6),
        )
        matches = detect_rectangle_bullish(make_df(closes))
        assert_single_confident_match(matches, "Rectangle Bullish")

    def test_no_match_before_enough_bars(self):
        closes = ramp(100, 105, 5)
        assert detect_rectangle_bullish(make_df(closes)) == []

    def test_no_match_without_breakout_confirmation(self):
        # Même range, mais la dernière clôture reste à l'intérieur : pas de
        # cassure confirmée.
        closes = path(
            ramp(100, 105, 5),
            ramp(105, 95, 5),
            ramp(95, 104.5, 5),
            ramp(104.5, 95.5, 5),
            ramp(95.5, 105.2, 5),
            ramp(105.2, 96, 5),
            ramp(96, 101, 6),
        )
        assert detect_rectangle_bullish(make_df(closes)) == []


class TestRectangleBearish:
    def test_detects_confirmed_rectangle_breakdown(self):
        # Même range que ci-dessus, mais cassure franche sous le support.
        closes = path(
            ramp(100, 105, 5),
            ramp(105, 95, 5),
            ramp(95, 104.5, 5),
            ramp(104.5, 95.5, 5),
            ramp(95.5, 105.2, 5),
            ramp(105.2, 96, 5),
            ramp(96, 88, 6),
        )
        matches = detect_rectangle_bearish(make_df(closes))
        assert_single_confident_match(matches, "Rectangle Bearish")

    def test_no_match_before_enough_bars(self):
        closes = ramp(105, 100, 5)
        assert detect_rectangle_bearish(make_df(closes)) == []


class TestBullPennant:
    def test_detects_confirmed_bull_pennant(self):
        # Mât impulsif haussier (+30% environ), puis petit triangle
        # convergent (sommets décroissants, creux croissants) resserré par
        # rapport au mât, puis cassure haussière dans le même sens que le mât.
        closes = path(
            ramp(100, 130, 9),  # mât
            ramp(130, 121, 4),
            ramp(121, 128, 4),
            ramp(128, 123, 4),
            ramp(123, 126.5, 4),
            ramp(126.5, 125, 3),
            ramp(125, 140, 2),  # cassure, même sens que le mât
        )
        matches = detect_bull_pennant(make_df(closes))
        assert_single_confident_match(matches, "Bull Pennant")

    def test_no_match_without_pole(self):
        # Pas de mât : simple bruit sans mouvement impulsif préalable.
        closes = path(
            ramp(100, 101, 10),
            ramp(101, 99, 3),
            ramp(99, 100.5, 3),
            ramp(100.5, 99.5, 3),
            ramp(99.5, 100.2, 3),
            ramp(100.2, 99.8, 3),
            ramp(99.8, 102, 4),
        )
        assert detect_bull_pennant(make_df(closes)) == []


class TestBearPennant:
    def test_detects_confirmed_bear_pennant(self):
        # Mât impulsif baissier, petit triangle convergent, cassure baissière
        # dans le même sens que le mât.
        closes = path(
            ramp(130, 100, 9),  # mât baissier
            ramp(100, 109, 4),
            ramp(109, 102, 4),
            ramp(102, 107, 4),
            ramp(107, 103.5, 4),
            ramp(103.5, 105, 3),
            ramp(105, 90, 2),  # cassure, même sens que le mât
        )
        matches = detect_bear_pennant(make_df(closes))
        assert_single_confident_match(matches, "Bear Pennant")

    def test_no_match_before_enough_bars(self):
        closes = ramp(130, 128, 5)
        assert detect_bear_pennant(make_df(closes)) == []
