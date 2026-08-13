import numpy as np

from engine.features import atr_pct, bb_percent_b, macd_hist_pct, position_vs_moving_averages, relative_volume, rsi_at, stochastic_k_at
from tests.test_patterns import make_df, ramp


def test_relative_volume_detects_a_volume_spike():
    closes = ramp(100, 110, 30)
    volumes = [1_000_000] * 29 + [5_000_000]
    df = make_df(closes, volumes=volumes)
    ratio = relative_volume(df, len(df) - 1)
    assert ratio is not None
    assert ratio > 4.0


def test_relative_volume_none_at_series_start():
    df = make_df(ramp(100, 110, 10))
    assert relative_volume(df, 0) is None


def test_atr_pct_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert atr_pct(df, 5, window=14) is None


def test_atr_pct_positive_on_volatile_series():
    rng = np.random.default_rng(0)
    closes = list(100 + np.cumsum(rng.normal(0, 1.5, 40)))
    df = make_df(closes)
    value = atr_pct(df, len(df) - 1, window=14)
    assert value is not None
    assert value > 0


def test_position_vs_moving_averages_none_with_short_history():
    df = make_df(ramp(100, 120, 50))
    assert position_vs_moving_averages(df, len(df) - 1) is None


def test_position_vs_moving_averages_available_with_enough_history():
    df = make_df(ramp(100, 150, 210))
    features = position_vs_moving_averages(df, len(df) - 1)
    assert features is not None
    assert set(features) == {"price_over_sma50", "price_over_sma200", "sma50_over_sma200"}
    # série strictement croissante : le prix termine au-dessus de ses moyennes mobiles
    assert features["price_over_sma50"] > 1.0
    assert features["price_over_sma200"] > 1.0


def test_rsi_at_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert rsi_at(df, 5, window=14) is None


def test_rsi_at_high_on_an_uninterrupted_rally():
    df = make_df(ramp(100, 150, 30))
    value = rsi_at(df, len(df) - 1, window=14)
    assert value is not None
    assert value > 90.0  # hausse ininterrompue -> RSI proche de 100 (voir engine.patterns.common.rsi)


def test_macd_hist_pct_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert macd_hist_pct(df, 5) is None


def test_macd_hist_pct_positive_on_an_uninterrupted_rally():
    df = make_df(ramp(100, 160, 60))
    value = macd_hist_pct(df, len(df) - 1)
    assert value is not None
    assert value > 0


def test_bb_percent_b_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert bb_percent_b(df, 5) is None


def test_bb_percent_b_near_one_on_an_uninterrupted_rally():
    """Une hausse continue laisse le prix coller à la bande haute -- %b
    proche de 1.0 (voir engine.patterns.common.bollinger_bands)."""
    df = make_df(ramp(100, 130, 30))
    value = bb_percent_b(df, len(df) - 1)
    assert value is not None
    assert value > 0.8


def test_stochastic_k_at_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert stochastic_k_at(df, 5) is None


def test_stochastic_k_at_high_on_an_uninterrupted_rally():
    df = make_df(ramp(100, 130, 30))
    value = stochastic_k_at(df, len(df) - 1)
    assert value is not None
    assert value > 90.0  # clôture au plus haut de la fenêtre -> %K proche de 100
