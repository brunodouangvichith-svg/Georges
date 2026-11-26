import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine

from engine.risk_metrics import compute_risk_metrics, sector_family, session_index
from engine.run_detection import load_prices, load_recent_prices
from ingestion import index_prices
from ingestion.models import PriceHistoryLong

TODAY = pd.Timestamp("2026-11-26")
DATES = pd.bdate_range(end=TODAY - pd.Timedelta(days=1), periods=300)


def _closes(returns) -> pd.Series:
    return pd.Series(100 * np.exp(np.cumsum(returns)), index=DATES[-len(returns) :])


def _frame(close: pd.Series, volume=1000) -> pd.DataFrame:
    """Comme en base : minuit heure de Paris, renvoyé en UTC."""
    index = close.index.tz_localize("Europe/Paris").tz_convert("UTC")
    return pd.DataFrame(
        {"open": close.values, "high": close.values + 1, "low": close.values - 1, "close": close.values, "volume": volume},
        index=index,
    )


def _random(seed: int, size: int = 300) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, 0.01, size)


def _one(prices, index_close=None, sectors=None, symbol="A"):
    sectors = sectors or {s: "Industrie / X" for s in prices}
    rows = compute_risk_metrics(prices, sectors, index_close, TODAY)
    return next(r for r in rows if r["symbol"] == symbol)


def test_session_dates_are_read_in_paris_time():
    stored = pd.DatetimeIndex(["2026-07-14 22:00", "2026-01-14 23:00"], tz="UTC")
    assert list(session_index(stored)) == [pd.Timestamp("2026-07-15"), pd.Timestamp("2026-01-15")]


def test_volume_atr_and_volatility():
    returns = _random(1)
    frame = _frame(_closes(returns))
    frame["volume"] = np.arange(1, 301) * 10
    row = _one({"A": frame})
    assert row["average_daily_volume"] == pytest.approx(np.mean(np.arange(281, 301) * 10))
    expected = np.std(returns[-252:], ddof=1) * np.sqrt(252) * 100
    assert row["volatility_pct"] == pytest.approx(expected)
    previous = frame["close"].shift(1)
    true_range = pd.concat([frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()], axis=1)
    assert row["atr"] == pytest.approx(true_range.max(axis=1).iloc[-14:].mean())
    assert row["atr_pct"] == pytest.approx(row["atr"] / frame.close.iloc[-1] * 100)
    assert row["as_of"] == DATES[-1].date()


def test_beta_and_correlations_against_index_and_sector():
    market = _random(2)
    prices = {"A": _frame(_closes(2 * market)), "B": _frame(_closes(market)), "C": _frame(_closes(market))}
    row = _one(prices, _closes(market))
    assert row["beta"] == pytest.approx(2.0)
    assert row["index_correlation"] == pytest.approx(1.0)
    assert row["sector_correlation"] == pytest.approx(1.0)
    assert row["sector_peers"] == 2
    assert row["sector_family"] == "Industrie"


def test_sector_excludes_itself_and_needs_two_peers():
    prices = {"A": _frame(_closes(_random(3))), "B": _frame(_closes(_random(4))), "C": _frame(_closes(_random(5)))}
    sectors = {"A": "Santé / Pharmacie", "B": "Santé / Biotechnologie", "C": "Assurance"}
    row = _one(prices, sectors=sectors)
    assert row["sector_correlation"] is None
    assert row["sector_peers"] == 0


def test_beta_uses_returns_over_common_sessions_only():
    index_close = _closes(_random(6))
    # Séances absentes d'un côté puis de l'autre : les rendements restent comparables.
    row = _one({"A": _frame(index_close.drop(DATES[[250, 270]]))}, index_close.drop(DATES[[260]]))
    assert row["beta"] == pytest.approx(1.0)
    assert row["index_correlation"] == pytest.approx(1.0)


def test_insufficient_history_gives_none_never_zero():
    market = _random(7)
    row = _one({"A": _frame(_closes(market[:252]))}, _closes(market))
    assert row["volatility_pct"] is None  # 251 rendements
    assert row["beta"] is None and row["index_correlation"] is None
    assert row["average_daily_volume"] is not None

    short = _one({"A": _frame(_closes(market[:14]))})
    assert short["atr"] is None and short["average_daily_volume"] is None

    full = _one({"A": _frame(_closes(market[:253]))})
    assert full["volatility_pct"] is not None


def test_one_year_window_rejects_a_series_with_a_long_hole():
    dates = pd.bdate_range(end=DATES[-1], periods=600)
    close = pd.Series(100 * np.exp(np.cumsum(_random(8, 600))), index=dates)
    holed = pd.concat([close.iloc[:200], close.iloc[-100:]])
    row = _one({"A": _frame(holed)}, close)
    assert row["volatility_pct"] is None and row["beta"] is None


def test_missing_index_and_symbol_without_prices():
    rows = compute_risk_metrics({"A": _frame(_closes(_random(9)))}, {"A": "Énergie", "Z": "Énergie"}, None, TODAY)
    a, z = rows
    assert a["beta"] is None and a["volatility_pct"] is not None
    assert z["symbol"] == "Z" and z["as_of"] is None and z["average_daily_volume"] is None


def test_todays_partial_session_and_zero_volumes_are_ignored():
    close = _closes(_random(10))
    close.index = pd.bdate_range(end=TODAY, periods=300)
    frame = _frame(close)
    frame.iloc[-1, frame.columns.get_loc("volume")] = 1
    frame.iloc[-2, frame.columns.get_loc("volume")] = 0
    row = _one({"A": frame})
    assert row["as_of"] < TODAY.date()
    assert row["average_daily_volume"] == 1000


def test_nan_close_is_filtered_and_results_are_json_safe():
    close = _closes(_random(11))
    close.iloc[-5] = np.nan
    row = _one({"A": _frame(close)})
    assert all(not isinstance(v, float) or np.isfinite(v) for v in row.values())
    assert row["volatility_pct"] is not None


def test_a_jump_above_fifty_percent_is_flagged_not_hidden():
    returns = _random(12)
    returns[-10] = np.log(3)
    row = _one({"A": _frame(_closes(returns))})
    assert row["suspect_jump_date"] == DATES[-10].date()
    assert row["volatility_pct"] is not None
    assert _one({"A": _frame(_closes(_random(12)))})["suspect_jump_date"] is None


def test_sector_family_matches_the_web_grouping():
    assert sector_family("Santé / Biotechnologie") == "Santé"
    assert sector_family("Assurance") == "Assurance"
    assert sector_family(None) == ""


def test_bulk_price_load_cleans_like_load_prices():
    """SQLite suffit ici (sans Docker) : même requête, même nettoyage."""
    engine = create_engine("sqlite://")
    PriceHistoryLong.__table__.create(engine)
    bar = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10}
    # ATO.PA a une rupture d'échelle connue le 06/12/2024 (engine/price_breaks.py).
    days = ["2024-12-02", "2024-12-09", "2024-12-10"]
    rows = [{"symbol": s, "ts": pd.Timestamp(d).to_pydatetime(), **bar} for s in ("ATO.PA", "AIR.PA") for d in days]
    with engine.begin() as conn:
        conn.execute(PriceHistoryLong.__table__.insert(), rows)

    bulk = load_recent_prices(engine, pd.Timestamp("2024-12-01").to_pydatetime())

    assert {symbol: len(df) for symbol, df in bulk.items()} == {"AIR.PA": 3, "ATO.PA": 2}
    for symbol, df in bulk.items():
        single = load_prices(engine, symbol)
        assert df.to_dict("list") == single.to_dict("list")


class _Ticker:
    calls = 0
    fail = False

    def __init__(self, symbol):
        assert symbol == "^FCHI"

    def history(self, **kwargs):
        _Ticker.calls += 1
        if _Ticker.fail:
            raise ConnectionError("hors ligne")
        index = pd.DatetimeIndex(["2026-11-24", "2026-11-25"]).tz_localize("Europe/Paris")
        return pd.DataFrame({"Close": [8000.0, 8010.0]}, index=index)


@pytest.fixture
def fake_yahoo(monkeypatch):
    _Ticker.calls, _Ticker.fail = 0, False
    monkeypatch.setattr(index_prices.yf, "Ticker", _Ticker)
    monkeypatch.setattr(index_prices, "_cache", {"closes": None, "expires_at": 0.0})
    return _Ticker


def test_index_closes_are_cached_and_dated_by_session(fake_yahoo):
    first = index_prices.cac40_closes()
    index_prices.cac40_closes()
    assert fake_yahoo.calls == 1
    assert list(first.index) == [pd.Timestamp("2026-11-24"), pd.Timestamp("2026-11-25")]


def test_index_drops_the_download_day_bar(fake_yahoo, monkeypatch):
    today = pd.Timestamp.now(tz="Europe/Paris").normalize()
    index = pd.DatetimeIndex([today - pd.Timedelta(days=1), today])
    monkeypatch.setattr(_Ticker, "history", lambda self, **kwargs: pd.DataFrame({"Close": [1.0, 2.0]}, index=index))
    assert list(index_prices.cac40_closes()) == [1.0]


def test_index_failure_degrades_without_hammering(fake_yahoo):
    fake_yahoo.fail = True
    assert index_prices.cac40_closes() is None
    assert index_prices.cac40_closes() is None
    assert fake_yahoo.calls == 1


def test_index_failure_serves_the_last_series(fake_yahoo):
    index_prices.cac40_closes()
    fake_yahoo.fail = True
    index_prices._cache["expires_at"] = 0.0
    assert len(index_prices.cac40_closes()) == 2
