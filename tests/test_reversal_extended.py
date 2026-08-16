"""Teste les figures de retournement ajoutées à `engine/patterns/reversal.py`
en plus des 5 déjà couvertes par `tests/test_patterns.py` : Triple Top/
Bottom, Rounding Top/Bottom, Diamond Top/Bottom.

Même principe que `tests/test_patterns.py` : séries synthétiques construites
en mémoire, sans DB ni réseau.
"""

from engine.patterns.reversal import (
    detect_diamond_bottom,
    detect_diamond_top,
    detect_rounding_bottom,
    detect_rounding_top,
    detect_triple_bottom,
    detect_triple_top,
)
from tests.test_patterns import assert_single_confident_match, make_df, path, ramp


class TestTripleTop:
    def test_detects_confirmed_triple_top(self):
        closes = path(
            ramp(100, 110, 7),  # sommet 1
            ramp(110, 102, 7),  # creux 1
            ramp(102, 110.2, 7),  # sommet 2
            ramp(110.2, 101, 7),  # creux 2
            ramp(101, 109.8, 7),  # sommet 3
            ramp(109.8, 95, 7),  # cassure sous le support
        )
        matches = detect_triple_top(make_df(closes))
        assert_single_confident_match(matches, "Triple Top")
        context = matches[0].context
        assert "top_1" in context and "top_2" in context and "top_3" in context
        assert "support" in context

    def test_no_match_with_only_two_tops(self):
        # Géométrie de Double Top (2 sommets seulement) : pas assez
        # d'extrema pour former un Triple Top.
        closes = path(ramp(100, 110, 7), ramp(110, 100, 9), ramp(100, 109.5, 9), ramp(109.5, 97, 9))
        assert detect_triple_top(make_df(closes)) == []

    def test_no_match_without_breakout_confirmation(self):
        # Même géométrie à 3 sommets, mais la dernière clôture ne casse pas
        # le support.
        closes = path(
            ramp(100, 110, 7),
            ramp(110, 102, 7),
            ramp(102, 110.2, 7),
            ramp(110.2, 101, 7),
            ramp(101, 109.8, 7),
            ramp(109.8, 105, 7),
        )
        assert detect_triple_top(make_df(closes)) == []


class TestTripleBottom:
    def test_detects_confirmed_triple_bottom(self):
        closes = path(
            ramp(100, 90, 7),  # creux 1
            ramp(90, 98, 7),  # sommet 1
            ramp(98, 90.2, 7),  # creux 2
            ramp(90.2, 99, 7),  # sommet 2
            ramp(99, 90.8, 7),  # creux 3
            ramp(90.8, 105, 7),  # cassure au-dessus de la résistance
        )
        matches = detect_triple_bottom(make_df(closes))
        assert_single_confident_match(matches, "Triple Bottom")
        context = matches[0].context
        assert "bottom_1" in context and "bottom_2" in context and "bottom_3" in context
        assert "resistance" in context

    def test_no_match_with_only_two_bottoms(self):
        closes = path(ramp(100, 90, 7), ramp(90, 100, 9), ramp(100, 90.5, 9), ramp(90.5, 103, 9))
        assert detect_triple_bottom(make_df(closes)) == []


class TestRoundingBottom:
    def test_detects_confirmed_rounding_bottom(self):
        # Parabole a>0 : close(x) = 0.1*(x-10)^2 + 95, sommet en x=10 (dans
        # les 60% centraux de la fenêtre de 30 barres) -> creux à 95, remonte
        # nettement au-dessus du rebord de départ (105) en fin de fenêtre.
        closes = [0.1 * (x - 10) ** 2 + 95 for x in range(30)]
        matches = detect_rounding_bottom(make_df(closes))
        assert_single_confident_match(matches, "Rounding Bottom")
        context = matches[0].context
        assert "rim" in context and "vertex" in context
        assert context["r_squared"] >= 0.5

    def test_no_match_when_vertex_outside_central_window(self):
        # Sommet de la parabole en x=-10 (hors fenêtre, avant son début) :
        # la courbe est monotone croissante sur toute la fenêtre, ce n'est
        # pas un vrai "arrondi" au sens géométrique exigé.
        closes = [0.05 * (x + 10) ** 2 + 90 for x in range(30)]
        assert detect_rounding_bottom(make_df(closes)) == []


class TestRoundingTop:
    def test_detects_confirmed_rounding_top(self):
        # Parabole a<0 : close(x) = -0.1*(x-10)^2 + 105, sommet en x=10,
        # redescend nettement sous le rebord de départ (95) en fin de fenêtre.
        closes = [-0.1 * (x - 10) ** 2 + 105 for x in range(30)]
        matches = detect_rounding_top(make_df(closes))
        assert_single_confident_match(matches, "Rounding Top")

    def test_no_match_on_upward_curve(self):
        # a>0 (courbe tournée vers le haut) : ne peut pas être un Rounding Top.
        closes = [0.1 * (x - 10) ** 2 + 95 for x in range(30)]
        assert detect_rounding_top(make_df(closes)) == []


def _diamond_pattern_closes(n_first: int, n_second: int, base: float, start_amp: float, peak_amp: float) -> list[float]:
    """Construit une séquence de clôtures oscillant autour de `base`, avec
    une amplitude qui croît de `start_amp` à `peak_amp` sur les `n_first`
    premiers pas puis redécroît de `peak_amp` à `start_amp` sur les
    `n_second` suivants -- fait osciller le range haut-bas par barre
    (proportionnel à la variation de clôture d'une barre à l'autre dans
    `make_df`) en expansion puis en contraction, la géométrie attendue par
    `_diamond`."""
    values = []
    sign = 1
    for i in range(n_first):
        amp = start_amp + (peak_amp - start_amp) * i / max(n_first - 1, 1)
        values.append(base + sign * amp)
        sign *= -1
    for i in range(n_second):
        amp = peak_amp - (peak_amp - start_amp) * i / max(n_second - 1, 1)
        values.append(base + sign * amp)
        sign *= -1
    return values


class TestDiamondTop:
    def test_detects_confirmed_diamond_top(self):
        preceding = ramp(85, 100, 10)  # tendance haussière avant le losange
        pattern = _diamond_pattern_closes(14, 15, base=100, start_amp=1, peak_amp=15)
        closes = preceding + pattern + [70]  # cassure sous le plus bas de la 2e moitié
        matches = detect_diamond_top(make_df(closes))
        assert_single_confident_match(matches, "Diamond Top")
        context = matches[0].context
        assert "breakout_level" in context and "widest_range" in context

    def test_no_match_without_preceding_uptrend(self):
        # Même losange, mais précédé d'une tendance baissière (pas haussière)
        # -> filtre dur de tendance préalable, pas un Diamond Top.
        preceding = ramp(100, 85, 10)
        pattern = _diamond_pattern_closes(14, 15, base=100, start_amp=1, peak_amp=15)
        closes = preceding + pattern + [70]
        assert detect_diamond_top(make_df(closes)) == []


class TestDiamondBottom:
    def test_detects_confirmed_diamond_bottom(self):
        preceding = ramp(100, 85, 10)  # tendance baissière avant le losange
        pattern = _diamond_pattern_closes(14, 15, base=100, start_amp=1, peak_amp=15)
        closes = preceding + pattern + [130]  # cassure au-dessus du plus haut de la 2e moitié
        matches = detect_diamond_bottom(make_df(closes))
        assert_single_confident_match(matches, "Diamond Bottom")

    def test_no_match_too_short(self):
        # Historique trop court pour couvrir la fenêtre du losange.
        closes = ramp(95, 105, 15)
        assert detect_diamond_bottom(make_df(closes)) == []
