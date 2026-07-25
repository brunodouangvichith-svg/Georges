import pandas as pd
import pytest

from engine.george_index import compute_george_index, momentum_pct, most_recent_active_confidence
from tests.test_patterns import make_df, ramp


def _patterns(rows):
    # Volontairement naïf (sans fuseau) : cohérent avec l'index de
    # `tests.test_patterns.make_df`, utilisé partout ailleurs dans ce fichier.
    df = pd.DataFrame(rows, columns=["symbol", "detected_at", "confidence"])
    df["detected_at"] = pd.to_datetime(df["detected_at"])
    return df


def test_most_recent_active_confidence_picks_highest_among_active():
    as_of = pd.Timestamp("2024-03-01")
    patterns = _patterns(
        [
            ("AAA", "2024-02-28", 60.0),  # actif, dans la fenêtre
            ("AAA", "2024-02-27", 90.0),  # actif aussi, confiance plus haute -> doit gagner
            ("AAA", "2024-01-01", 99.0),  # trop ancien -> ignoré
            ("BBB", "2024-02-28", 50.0),
        ]
    )
    assert most_recent_active_confidence(patterns, "AAA", as_of) == 90.0


def test_most_recent_active_confidence_none_when_no_active_pattern():
    as_of = pd.Timestamp("2024-03-01")
    patterns = _patterns([("AAA", "2024-01-01", 90.0)])
    assert most_recent_active_confidence(patterns, "AAA", as_of) is None


def test_momentum_pct_positive_on_rising_series():
    df = make_df(ramp(100, 130, 25))
    m = momentum_pct(df, window=20)
    assert m is not None
    assert m > 0


def test_momentum_pct_none_with_short_history():
    df = make_df(ramp(100, 110, 10))
    assert momentum_pct(df, window=20) is None


def test_compute_george_index_none_when_no_active_pattern_in_basket():
    df = make_df(ramp(100, 110, 30))
    patterns = _patterns([("AAA", "2024-01-01", 90.0)])  # trop ancien -> pas actif
    index = compute_george_index([("AAA", 1.0)], patterns, {"AAA": df}, df.index[-1])
    assert index is None


def test_compute_george_index_weighted_average_of_active_confidences():
    flat_a = make_df([100.0] * 30)
    flat_b = make_df([100.0] * 30)
    as_of = flat_a.index[-1]
    patterns = _patterns([("AAA", as_of, 80.0), ("BBB", as_of, 40.0)])
    price_frames = {"AAA": flat_a, "BBB": flat_b}

    # séries plates : momentum et volume relatif neutres -> l'index est exactement le score de base
    index_equal = compute_george_index([("AAA", 1.0), ("BBB", 1.0)], patterns, price_frames, as_of)
    assert index_equal == pytest.approx(60.0)

    index_weighted = compute_george_index([("AAA", 9.0), ("BBB", 1.0)], patterns, price_frames, as_of)
    assert index_weighted == pytest.approx(76.0)


def test_compute_george_index_momentum_shifts_index_within_cap():
    flat = make_df([100.0] * 30)
    rising = make_df(ramp(100, 140, 30))  # momentum bien au-delà du plafond +15 %
    falling = make_df(ramp(100, 70, 30))  # momentum bien au-delà du plafond -15 %
    as_of = flat.index[-1]  # make_df démarre toujours à la même date -> grilles alignées
    patterns = _patterns([("AAA", as_of, 70.0)])

    index_flat = compute_george_index([("AAA", 1.0)], patterns, {"AAA": flat}, as_of)
    index_rising = compute_george_index([("AAA", 1.0)], patterns, {"AAA": rising}, as_of)
    index_falling = compute_george_index([("AAA", 1.0)], patterns, {"AAA": falling}, as_of)

    assert index_flat == pytest.approx(70.0)
    assert index_rising == pytest.approx(70.0 * 1.15)
    assert index_falling == pytest.approx(70.0 * 0.85)


def test_compute_george_index_clipped_to_0_100():
    flat = make_df([100.0] * 30)
    as_of = flat.index[-1]
    patterns = _patterns([("AAA", as_of, 100.0)])
    index = compute_george_index([("AAA", 1.0)], patterns, {"AAA": flat}, as_of)
    assert index <= 100.0
