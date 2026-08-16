"""Teste `engine/patterns/crossover.py` (Golden Cross / Death Cross) sur des
séries de prix synthétiques construites pour croiser SMA50/SMA200 exactement
à la barre voulue.

Contrairement aux figures géométriques de `test_patterns.py`, un croisement
de moyennes mobiles ne peut pas être positionné "à l'oeil" par construction
d'un chemin de rampes : il faut d'abord fabriquer une série assez longue pour
que le croisement se produise quelque part, puis retrouver la barre exacte du
croisement (via les mêmes fonctions `sma` que le détecteur) et tronquer la
série pile à cette barre pour tester l'événement, pas l'état qui suit.
"""

import pandas as pd

from engine.patterns.common import sma
from engine.patterns.crossover import SMA_LONG, SMA_SHORT, detect_death_cross, detect_golden_cross
from tests.test_patterns import make_df, path, ramp


def _closes_up_to_crossover(closes: list[float], bullish: bool) -> list[float]:
    """Tronque `closes` pile à la première barre où SMA50 croise SMA200 dans
    le sens `bullish` (True = croisement à la hausse, False = à la baisse).
    Lève `AssertionError` si aucun croisement n'est trouvé (série de test mal
    calibrée)."""
    close = pd.Series(closes, dtype=float)
    sma50, sma200 = sma(close, SMA_SHORT), sma(close, SMA_LONG)
    for i in range(1, len(close)):
        p50, p200, c50, c200 = sma50.iloc[i - 1], sma200.iloc[i - 1], sma50.iloc[i], sma200.iloc[i]
        if pd.isna(p50) or pd.isna(p200) or pd.isna(c50) or pd.isna(c200):
            continue
        crossed = (p50 <= p200 and c50 > c200) if bullish else (p50 >= p200 and c50 < c200)
        if crossed:
            return closes[: i + 1]
    raise AssertionError("aucun croisement trouve dans la serie synthetique - a recalibrer")


# Longue phase plate (les deux moyennes s'égalisent autour de 100) suivie
# d'une tendance nette qui finit par faire croiser SMA50 au-dessus/en dessous
# de SMA200.
_UP_CLOSES = path(ramp(100, 100, 200), ramp(100, 160, 100))
_DOWN_CLOSES = path(ramp(100, 100, 200), ramp(100, 40, 100))


class TestGoldenCross:
    def test_detects_golden_cross_at_crossover_bar(self):
        closes = _closes_up_to_crossover(_UP_CLOSES, bullish=True)
        matches = detect_golden_cross(make_df(closes))
        assert len(matches) == 1
        match = matches[0]
        assert match.pattern_type == "Golden Cross"
        assert 0.0 <= match.confidence <= 100.0
        assert match.context["sma50"] > match.context["sma200"]

    def test_no_match_insufficient_history(self):
        # Bien moins que SMA_LONG + 1 barres : sma200 n'est jamais défini.
        closes = ramp(100, 160, SMA_LONG // 2)
        assert detect_golden_cross(make_df(closes)) == []

    def test_no_match_once_past_the_crossover_bar(self):
        # Détecteur d'événement, pas d'état : une fois le croisement passé,
        # SMA50 reste au-dessus de SMA200 pendant des barres supplémentaires
        # sans qu'un nouveau croisement se reproduise -> plus de détection.
        crossover_closes = _closes_up_to_crossover(_UP_CLOSES, bullish=True)
        extended = crossover_closes + [crossover_closes[-1] * 1.001] * 5
        assert detect_golden_cross(make_df(extended)) == []


class TestDeathCross:
    def test_detects_death_cross_at_crossover_bar(self):
        closes = _closes_up_to_crossover(_DOWN_CLOSES, bullish=False)
        matches = detect_death_cross(make_df(closes))
        assert len(matches) == 1
        match = matches[0]
        assert match.pattern_type == "Death Cross"
        assert 0.0 <= match.confidence <= 100.0
        assert match.context["sma50"] < match.context["sma200"]

    def test_no_match_insufficient_history(self):
        closes = ramp(100, 40, SMA_LONG // 2)
        assert detect_death_cross(make_df(closes)) == []

    def test_no_match_on_a_rising_series(self):
        # Mauvais contexte de tendance : une série qui ne fait que monter ne
        # produit jamais de croisement baissier.
        assert detect_death_cross(make_df(_UP_CLOSES)) == []
