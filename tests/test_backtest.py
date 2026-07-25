import pytest

from engine.backtest import (
    build_sample,
    build_training_set,
    compute_market_trend,
    forward_returns,
    is_bullish,
    label_success,
)
from tests.test_patterns import make_df, ramp


def test_is_bullish_classifies_known_patterns():
    assert is_bullish("Bull Flag") is True
    assert is_bullish("Double Top") is False
    assert is_bullish("Breakdown") is False


def test_forward_returns_matches_expected_percentage():
    df = make_df([100, 100, 100, 100, 100, 110, 100, 100, 100, 100, 100, 121])
    returns = forward_returns(df, at_idx=4, horizons=(1, 7))
    assert returns[1] == pytest.approx(10.0)
    assert returns[7] == pytest.approx(21.0)


def test_forward_returns_omits_horizons_beyond_series_end():
    df = make_df(ramp(100, 110, 10))
    returns = forward_returns(df, at_idx=8, horizons=(1, 5))
    assert 1 in returns
    assert 5 not in returns


def test_label_success_bullish_vs_bearish():
    assert label_success(1.0, "Bull Flag") is True
    assert label_success(-1.0, "Bull Flag") is False
    assert label_success(-1.0, "Double Top") is True
    assert label_success(1.0, "Double Top") is False


def test_compute_market_trend_averages_across_universe():
    up = make_df(ramp(100, 120, 25))  # +20% sur la fenêtre
    down = make_df(ramp(100, 90, 25))  # -10% sur la fenêtre
    trend = compute_market_trend({"UP": up, "DOWN": down}, at_date=up.index[-1], lookback=20)
    assert trend is not None
    assert 0 < trend < 20  # moyenne des deux mouvements, positive puisque +20% domine -10%


def test_compute_market_trend_none_when_no_symbol_has_enough_history():
    short = make_df(ramp(100, 105, 5))
    assert compute_market_trend({"SHORT": short}, at_date=short.index[-1], lookback=20) is None


def test_build_sample_none_when_too_recent_to_evaluate():
    df = make_df(ramp(100, 110, 15))
    sample = build_sample(df, at_idx=len(df) - 1, pattern_type="Bull Flag", sector="Technologie", market_trend=1.0)
    assert sample is None


def test_build_sample_has_expected_keys_and_labels():
    df = make_df(ramp(100, 200, 60))
    sample = build_sample(df, at_idx=10, pattern_type="Bull Flag", sector="Technologie", market_trend=2.5)
    assert sample is not None
    assert sample["pattern_type"] == "Bull Flag"
    assert sample["sector"] == "Technologie"
    assert sample["market_trend"] == 2.5
    for h in (5, 10, 20):
        assert f"return_{h}" in sample
        assert f"success_{h}" in sample
    # série strictement croissante : toutes les figures haussières réussissent
    assert sample["success_5"] is True
    assert sample["success_20"] is True


def test_build_training_set_drops_none_samples():
    df_long = make_df(ramp(100, 200, 60))
    df_short = make_df(ramp(100, 110, 15))
    samples = [
        build_sample(df_long, 10, "Bull Flag", "Technologie", 1.0),
        build_sample(df_short, len(df_short) - 1, "Bull Flag", "Technologie", 1.0),
    ]
    dataset = build_training_set(samples)
    assert len(dataset) == 1
