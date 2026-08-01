import numpy as np
import pandas as pd

from engine.carry_index import (
    carry_differential,
    compute_carry_score,
    cot_crowding_score,
    decide_for_crowding,
    realized_volatility,
)


def _price_df(closes):
    index = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"close": closes}, index=index)


def test_realized_volatility_none_with_short_history():
    df = _price_df([100.0] * 10)
    assert realized_volatility(df, window=20) is None


def test_realized_volatility_zero_on_flat_series():
    df = _price_df([100.0] * 25)
    vol = realized_volatility(df, window=20)
    assert vol == 0.0


def test_realized_volatility_positive_on_noisy_series():
    rng = np.random.default_rng(42)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 25)))
    df = _price_df(closes)
    vol = realized_volatility(df, window=20)
    assert vol is not None
    assert vol > 0


def test_carry_differential_is_simple_subtraction():
    assert carry_differential(target_rate_pct=6.76, funding_rate_pct=1.27) == 5.49


def test_cot_crowding_score_scales_with_position_skew():
    # Écart long/short important par rapport à l'open interest -> score élevé.
    assert cot_crowding_score(lev_money_long=10, lev_money_short=90, open_interest_all=100) == 80.0
    # Long/short équilibrés -> score nul.
    assert cot_crowding_score(lev_money_long=50, lev_money_short=50, open_interest_all=100) == 0.0


def test_cot_crowding_score_none_when_open_interest_zero():
    assert cot_crowding_score(lev_money_long=10, lev_money_short=20, open_interest_all=0) is None


def test_decide_for_crowding_thresholds():
    assert decide_for_crowding(80) == "Alléger"
    assert decide_for_crowding(65) == "Surveiller"
    assert decide_for_crowding(30) == "Achat"
    assert decide_for_crowding(None) == "Achat"  # repli neutre, pas de blocage


def test_compute_carry_score_assembles_all_fields():
    df = _price_df([100.0] * 25)  # vol nulle, mais calculable (25 > 20 séances)
    cot = {"lev_money_long": 76752, "lev_money_short": 178742, "open_interest_all": 432366}
    score = compute_carry_score(funding_rate_pct=1.27, target_rate_pct=6.76, fx_prices=df, cot=cot)
    assert score["carry_pct"] == 5.49
    assert score["realized_vol_pct"] == 0.0
    assert score["carry_vol_ratio"] is None  # ratio indéfini si la vol réalisée est nulle
    assert score["cot_crowding_score"] is not None
    assert score["decision"] in ("Achat", "Surveiller", "Alléger")


def test_compute_carry_score_returns_none_fields_when_data_missing():
    score = compute_carry_score(funding_rate_pct=None, target_rate_pct=6.76, fx_prices=None, cot=None)
    assert score["carry_pct"] is None
    assert score["realized_vol_pct"] is None
    assert score["carry_vol_ratio"] is None
    assert score["cot_crowding_score"] is None
    assert score["decision"] == "Achat"  # repli neutre quand la saturation est inconnue
