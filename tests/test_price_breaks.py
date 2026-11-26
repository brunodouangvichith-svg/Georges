"""Ruptures d'échelle connues (`engine/price_breaks.py`) et signalement des
sauts récents (`ingestion/price_history.py`). SQLite en mémoire pour
`load_prices` : ni Docker ni réseau."""

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers.securities import list_security_prices
from engine.price_breaks import FIRST_USABLE_SESSION, trim_before_break
from engine.run_detection import load_prices
from ingestion.models import PriceHistoryLong, Security
from ingestion.price_history import JUMP_CHECK_SESSIONS, recent_price_jumps


def _frame(index, closes=None) -> pd.DataFrame:
    return pd.DataFrame({"close": closes if closes is not None else [1.0] * len(index)}, index=index)


def test_symbol_without_break_is_unchanged():
    df = _frame(pd.bdate_range("2024-11-01", "2024-12-20"))
    assert trim_before_break("MC.PA", df) is df


@pytest.mark.parametrize("symbol, first", sorted(FIRST_USABLE_SESSION.items()))
def test_history_before_the_break_is_dropped(symbol, first):
    start = pd.Timestamp(first)
    df = _frame(pd.bdate_range(start - pd.Timedelta(days=30), start + pd.Timedelta(days=30)))
    trimmed = trim_before_break(symbol, df)
    assert trimmed.index[0] == start
    assert trimmed.index[-1] == df.index[-1]


@pytest.mark.parametrize("tz", ["Europe/Paris", "UTC"])
def test_paris_session_date_is_used_whatever_the_timezone(tz):
    # Minuit à Paris le 06/12 = 05/12 23 h UTC, tel que la base le renvoie.
    index = pd.DatetimeIndex(["2024-12-05", "2024-12-06", "2024-12-09"], tz="Europe/Paris").tz_convert(tz)
    trimmed = trim_before_break("ATO.PA", _frame(index, [1778.0, 26.0, 27.0]))
    assert list(trimmed["close"]) == [26.0, 27.0]


def test_load_prices_only_returns_the_usable_segment():
    engine = create_engine("sqlite://")
    PriceHistoryLong.__table__.create(engine)
    rows = [
        {"symbol": symbol, "ts": ts.to_pydatetime(), "open": c, "high": c, "low": c, "close": c, "volume": 1}
        for symbol in ("ATO.PA", "MC.PA")
        for ts, c in zip(pd.to_datetime(["2024-12-04", "2024-12-05", "2024-12-06"]), [3390.0, 1778.0, 26.0])
    ]
    with engine.begin() as conn:
        conn.execute(PriceHistoryLong.__table__.insert(), rows)

    assert list(load_prices(engine, "ATO.PA")["close"]) == [26.0]
    assert len(load_prices(engine, "MC.PA")) == 3


@pytest.mark.parametrize("symbol, kept", [("ATO.PA", 1), ("MC.PA", 3)])
def test_chart_prices_cover_the_same_sessions_as_the_analysis(symbol, kept):
    """Le graphique replace les index d'une figure à partir de `total` : la
    route doit compter les mêmes séances que `load_prices`."""
    engine = create_engine("sqlite://")
    Security.__table__.create(engine)
    PriceHistoryLong.__table__.create(engine)
    sessions = pd.DatetimeIndex(["2024-12-04", "2024-12-05", "2024-12-06"], tz="Europe/Paris")
    with engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            {"symbol": symbol, "name": symbol, "sector": "Test", "country": "FR", "currency": "EUR"},
        )
        conn.execute(
            PriceHistoryLong.__table__.insert(),
            # Heure de Paris sans fuseau : SQLite compare les dates en texte.
            [
                {"symbol": symbol, "ts": ts.tz_localize(None).to_pydatetime(),
                 "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
                for ts in sessions
            ],
        )

    with Session(engine) as db:
        page = list_security_prices(symbol, limit=250, offset=0, db=db)

    assert page.total == len(page.items) == kept == len(load_prices(engine, symbol))


def test_recent_jumps_are_reported_in_both_directions():
    index = pd.bdate_range("2024-01-01", periods=6)
    df = _frame(index, [10.0, 10.0, 25.0, 24.0, 9.0, 9.5])
    assert [(ts, round(r, 3)) for ts, r in recent_price_jumps(df)] == [(index[2], 2.5), (index[4], 0.375)]


def test_old_jumps_and_empty_frames_report_nothing():
    closes = [10.0, 100.0] + [150.0] * JUMP_CHECK_SESSIONS
    assert recent_price_jumps(_frame(pd.bdate_range("2024-01-01", periods=len(closes)), closes)) == []
    assert recent_price_jumps(_frame(pd.DatetimeIndex([]), [])) == []
