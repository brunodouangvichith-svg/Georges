"""Teste les nouveaux détecteurs de `engine/patterns/candlestick.py` (Harami,
Three White Soldiers/Three Black Crows, Kicker, Dragonfly Doji, Marubozu,
Inside Bar Breakout, Outside Bar) — même discipline que
`tests/test_candlestick.py` : séries construites à la main pour suivre
exactement la géométrie attendue, pas de données aléatoires.

Réutilise `_candle_df` (dupliqué depuis `tests/test_candlestick.py`, même
convention de duplication que les helpers `_rsi_at_last`/`_macd_line_at_last`
déjà dupliqués par fichier dans `engine/patterns/`) pour contrôler
précisément l'OHLC des bougies de signal — `test_patterns.make_df` seul ne
suffit pas ici : ses mèches, dérivées uniquement des clôtures, sont toujours
symétriques (~0.2 % de part et d'autre), ce qui ne peut jamais produire les
formes asymétriques (gap total, mèche unique dominante, corps quasi nul...)
que ces figures exigent.
"""

import pandas as pd

from engine.patterns.candlestick import (
    detect_bearish_harami,
    detect_bearish_inside_bar,
    detect_bearish_kicker,
    detect_bearish_marubozu,
    detect_bearish_outside_bar,
    detect_bullish_harami,
    detect_bullish_inside_bar,
    detect_bullish_kicker,
    detect_bullish_marubozu,
    detect_bullish_outside_bar,
    detect_dragonfly_doji,
    detect_three_black_crows,
    detect_three_white_soldiers,
)
from tests.test_patterns import make_df, path, ramp


def _candle_df(trend_closes: list[float], signal_candles: list[dict]) -> pd.DataFrame:
    """Même helper que `tests/test_candlestick.py:_candle_df` — dupliqué
    plutôt qu'importé, cohérent avec la convention de ce projet de ne pas
    faire dépendre un module de test d'un autre (chaque fichier de test
    reconstruit ses propres petits helpers, comme le font déjà les
    détecteurs eux-mêmes pour `_rsi_at_last`/`_macd_line_at_last`)."""
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


DOWNTREND = path(ramp(120, 100, 13))
UPTREND = path(ramp(100, 120, 13))
FLAT = [110.0] * 13


class TestHarami:
    def test_bullish_harami_after_downtrend(self):
        df = _candle_df(
            DOWNTREND,
            [
                {"open": 100.0, "high": 100.2, "low": 94.0, "close": 94.5},
                {"open": 96.0, "high": 97.3, "low": 95.8, "close": 97.0},
            ],
        )
        assert_single_confident_match(detect_bullish_harami(df), "Bullish Harami")

    def test_bearish_harami_after_uptrend(self):
        df = _candle_df(
            UPTREND,
            [
                {"open": 120.0, "high": 126.0, "low": 119.8, "close": 125.5},
                {"open": 124.0, "high": 124.3, "low": 122.7, "close": 123.0},
            ],
        )
        assert_single_confident_match(detect_bearish_harami(df), "Bearish Harami")

    def test_no_match_without_trend_confirmation(self):
        # Même géométrie de containment (petit corps dans le corps
        # précédent), mais après la tendance opposée à celle attendue.
        bullish_shape = [
            {"open": 100.0, "high": 100.2, "low": 94.0, "close": 94.5},
            {"open": 96.0, "high": 97.3, "low": 95.8, "close": 97.0},
        ]
        bearish_shape = [
            {"open": 120.0, "high": 126.0, "low": 119.8, "close": 125.5},
            {"open": 124.0, "high": 124.3, "low": 122.7, "close": 123.0},
        ]
        assert detect_bullish_harami(_candle_df(UPTREND, bullish_shape)) == []
        assert detect_bearish_harami(_candle_df(DOWNTREND, bearish_shape)) == []


class TestThreeSoldiersAndCrows:
    SOLDIERS_SHAPE = [
        {"open": 100.0, "high": 103.3, "low": 99.8, "close": 103.0},
        {"open": 101.5, "high": 105.8, "low": 101.3, "close": 105.5},
        {"open": 104.0, "high": 108.3, "low": 103.8, "close": 108.0},
    ]
    CROWS_SHAPE = [
        {"open": 120.0, "high": 120.2, "low": 116.7, "close": 117.0},
        {"open": 118.5, "high": 118.7, "low": 114.2, "close": 114.5},
        {"open": 116.0, "high": 116.2, "low": 111.2, "close": 111.5},
    ]

    def test_three_white_soldiers_after_downtrend(self):
        df = _candle_df(DOWNTREND, self.SOLDIERS_SHAPE)
        assert_single_confident_match(detect_three_white_soldiers(df), "Three White Soldiers")

    def test_three_black_crows_after_uptrend(self):
        df = _candle_df(UPTREND, self.CROWS_SHAPE)
        assert_single_confident_match(detect_three_black_crows(df), "Three Black Crows")

    def test_three_white_soldiers_no_match_after_uptrend(self):
        # Géométrie valide, mais Three White Soldiers n'accepte qu'un
        # contexte précédent baissier ou plat, jamais haussier.
        df = _candle_df(UPTREND, self.SOLDIERS_SHAPE)
        assert detect_three_white_soldiers(df) == []

    def test_three_white_soldiers_no_match_on_thin_bodies_with_opposite_wick(self):
        # Régression : bug réel trouvé en revue -- 3 bougies au corps
        # minuscule (~5% du range) flanquées d'une grande mèche du côté NON
        # contraint (basse, pour des "Soldiers" qui ne bornaient que la mèche
        # haute) passaient toutes les vérifications géométriques d'origine et
        # étaient détectées comme "Three White Soldiers", alors qu'aucun
        # chartiste n'appellerait ça 3 longues bougies vertes. Corrigé par
        # SOLDIER_MIN_BODY_RATIO (corps réellement "long") + le plafonnement
        # de l'ombre opposée en plus de l'ombre de poursuite.
        thin_body_shape = [
            {"open": 100.0, "high": 100.6, "low": 90.0, "close": 100.5},
            {"open": 100.2, "high": 100.8, "low": 90.2, "close": 100.7},
            {"open": 100.4, "high": 101.0, "low": 90.4, "close": 100.9},
        ]
        df = _candle_df(DOWNTREND, thin_body_shape)
        assert detect_three_white_soldiers(df) == []

    def test_three_black_crows_no_match_on_flat_trend(self):
        # Contrairement à Three White Soldiers, Three Black Crows exige une
        # tendance haussière précédente stricte : un contexte plat ne
        # suffit pas (pas de variante "de continuation" pour les corbeaux).
        df = _candle_df(FLAT, self.CROWS_SHAPE)
        assert detect_three_black_crows(df) == []


class TestKicker:
    def test_bullish_kicker(self):
        df = _candle_df(
            DOWNTREND,
            [
                {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
                {"open": 106.5, "high": 110.3, "low": 106.0, "close": 110.0},
            ],
        )
        assert_single_confident_match(detect_bullish_kicker(df), "Bullish Kicker")

    def test_bearish_kicker(self):
        df = _candle_df(
            UPTREND,
            [
                {"open": 100.0, "high": 105.2, "low": 99.8, "close": 105.0},
                {"open": 98.5, "high": 99.0, "low": 94.7, "close": 95.0},
            ],
        )
        assert_single_confident_match(detect_bearish_kicker(df), "Bearish Kicker")

    def test_no_match_without_full_range_gap(self):
        # Les amplitudes se chevauchent encore (comme un avalement) : pas de
        # gap total, donc pas un Kicker.
        overlap_bullish = [
            {"open": 105.0, "high": 105.2, "low": 99.8, "close": 100.0},
            {"open": 101.0, "high": 104.3, "low": 100.7, "close": 104.0},
        ]
        overlap_bearish = [
            {"open": 100.0, "high": 105.2, "low": 99.8, "close": 105.0},
            {"open": 104.0, "high": 104.3, "low": 100.7, "close": 101.0},
        ]
        assert detect_bullish_kicker(_candle_df(DOWNTREND, overlap_bullish)) == []
        assert detect_bearish_kicker(_candle_df(UPTREND, overlap_bearish)) == []


class TestDragonflyDoji:
    SHAPE = {"open": 99.9, "high": 100.0, "low": 90.0, "close": 100.0}

    def test_dragonfly_doji_after_downtrend(self):
        df = _candle_df(DOWNTREND, [self.SHAPE])
        assert_single_confident_match(detect_dragonfly_doji(df), "Dragonfly Doji")

    def test_no_match_after_uptrend(self):
        # Même silhouette en "T", mais un retournement haussier n'a de sens
        # qu'après une tendance baissière (§2.1 de la synthèse Kabbaj).
        df = _candle_df(UPTREND, [self.SHAPE])
        assert detect_dragonfly_doji(df) == []


class TestMarubozu:
    def test_bullish_marubozu(self):
        df = _candle_df(DOWNTREND, [{"open": 100.1, "high": 110.0, "low": 100.0, "close": 109.9}])
        assert_single_confident_match(detect_bullish_marubozu(df), "Bullish Marubozu")

    def test_bearish_marubozu(self):
        df = _candle_df(UPTREND, [{"open": 109.9, "high": 110.0, "low": 100.0, "close": 100.1}])
        assert_single_confident_match(detect_bearish_marubozu(df), "Bearish Marubozu")

    def test_no_match_with_large_shadows(self):
        # Mêmes bornes haut/bas et sens de bougie, mais des mèches bien
        # au-delà de `MARUBOZU_MAX_SHADOW_RATIO` : ce n'est plus une bougie
        # "pleine".
        wide_bullish = {"open": 102.0, "high": 110.0, "low": 95.0, "close": 106.0}
        wide_bearish = {"open": 106.0, "high": 110.0, "low": 95.0, "close": 100.0}
        assert detect_bullish_marubozu(_candle_df(DOWNTREND, [wide_bullish])) == []
        assert detect_bearish_marubozu(_candle_df(UPTREND, [wide_bearish])) == []


class TestInsideBarBreakout:
    MOTHER = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 102.0}
    INSIDE = {"open": 102.0, "high": 105.0, "low": 100.0, "close": 103.0}

    def test_bullish_inside_bar_breakout(self):
        breakout = {"open": 104.0, "high": 107.2, "low": 103.8, "close": 107.0}
        df = _candle_df(DOWNTREND, [self.MOTHER, self.INSIDE, breakout])
        assert_single_confident_match(detect_bullish_inside_bar(df), "Bullish Inside Bar")

    def test_bearish_inside_bar_breakout(self):
        breakout = {"open": 101.0, "high": 101.5, "low": 97.5, "close": 98.0}
        df = _candle_df(UPTREND, [self.MOTHER, self.INSIDE, breakout])
        assert_single_confident_match(detect_bearish_inside_bar(df), "Bearish Inside Bar")

    def test_no_match_without_breakout_confirmation(self):
        # Mother bar + inside bar valides, mais la 3e bougie clôture encore
        # à l'intérieur du range de l'inside bar : pas de cassure, pas de
        # figure confirmée (ni haussière ni baissière).
        no_breakout = {"open": 102.5, "high": 104.5, "low": 100.5, "close": 102.0}
        df = _candle_df(DOWNTREND, [self.MOTHER, self.INSIDE, no_breakout])
        assert detect_bullish_inside_bar(df) == []
        assert detect_bearish_inside_bar(df) == []


class TestOutsideBar:
    PREV = {"open": 101.0, "high": 105.0, "low": 100.0, "close": 102.0}

    def test_bullish_outside_bar(self):
        curr = {"open": 98.0, "high": 108.0, "low": 97.0, "close": 107.0}
        df = _candle_df(DOWNTREND, [self.PREV, curr])
        assert_single_confident_match(detect_bullish_outside_bar(df), "Bullish Outside Bar")

    def test_bearish_outside_bar(self):
        curr = {"open": 106.0, "high": 108.0, "low": 97.0, "close": 98.0}
        df = _candle_df(UPTREND, [self.PREV, curr])
        assert_single_confident_match(detect_bearish_outside_bar(df), "Bearish Outside Bar")

    def test_no_match_when_close_stays_in_middle_third(self):
        # Le range englobe bien celui de la précédente (condition
        # d'"outside bar" remplie), mais la clôture reste dans le tiers
        # central de son propre range : ni pression acheteuse ni vendeuse
        # assez nette pour l'un ou l'autre sens.
        curr = {"open": 104.0, "high": 108.0, "low": 97.0, "close": 102.0}
        df = _candle_df(DOWNTREND, [self.PREV, curr])
        assert detect_bullish_outside_bar(df) == []
        assert detect_bearish_outside_bar(df) == []


class TestInsufficientOrNonQualifyingHistory:
    """Réutilise `make_df` (contrairement aux classes ci-dessus, aucune
    bougie de signal explicite n'est nécessaire ici) pour vérifier qu'un
    historique court et strictement monotone — donc sans la moindre
    géométrie de bougie exploitable ni assez de recul pour `TREND_CONTEXT_
    BARS` — ne fait jamais planter les nouveaux détecteurs, seulement
    renvoyer `[]`, comme l'exige la convention `common.py`."""

    def test_short_monotonic_history_returns_empty_list(self):
        df = make_df(path(ramp(100, 105, 5)))
        assert detect_bullish_harami(df) == []
        assert detect_bearish_harami(df) == []
        assert detect_three_white_soldiers(df) == []
        assert detect_three_black_crows(df) == []
        assert detect_bullish_inside_bar(df) == []
        assert detect_bearish_inside_bar(df) == []
