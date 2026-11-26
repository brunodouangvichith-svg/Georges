"""Tests purs (pas de DB, pas de réseau) du backtest walk-forward des figures."""

import math

import pandas as pd
import pytest

from engine.backtest_detectors import (
    Costs,
    baseline_returns,
    generate_signals,
    run_trades,
    simulate_trade,
    summarize,
    verdict,
)

NO_COSTS = Costs(commission=0.0, slippage=0.0, ftt=0.0)


def ohlc(rows):
    """`rows` = [(open, high, low, close), ...] sur des jours ouvrés consécutifs."""
    idx = pd.bdate_range("2024-01-01", periods=len(rows))
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["volume"] = 1_000_000.0
    return df


def test_long_trade_hits_target_at_target_price():
    df = ohlc([(100, 100, 100, 100), (100, 101, 99, 100), (100, 111, 99, 110)])
    t = simulate_trade(df, 0, True, take_profit=110, stop_loss=95, costs=NO_COSTS, french_equity=False)
    assert t["outcome"] == "objectif"
    assert t["exit"] == 110
    assert t["gross_return"] == pytest.approx(0.10)
    assert t["bars_held"] == 2


def test_stop_wins_when_stop_and_target_touched_same_session():
    df = ohlc([(100, 100, 100, 100), (100, 112, 94, 100)])
    t = simulate_trade(df, 0, True, take_profit=110, stop_loss=95, costs=NO_COSTS, french_equity=False)
    assert t["outcome"] == "stop"
    assert t["exit"] == 95


def test_gap_through_stop_exits_at_open_not_stop():
    df = ohlc([(100, 100, 100, 100), (100, 101, 99, 100), (90, 91, 88, 89)])
    t = simulate_trade(df, 0, True, take_profit=110, stop_loss=95, costs=NO_COSTS, french_equity=False)
    assert t["outcome"] == "stop"
    assert t["exit"] == 90  # pire que le stop : l'écart d'ouverture est subi


def test_time_stop_exits_at_close_of_last_session():
    rows = [(100, 100, 100, 100)] + [(100, 102, 98, 101)] * 5
    t = simulate_trade(ohlc(rows), 0, True, 120, 90, NO_COSTS, False, max_hold=3)
    assert t["outcome"] == "duree"
    assert t["bars_held"] == 3
    assert t["exit"] == 101


def test_entry_gapping_past_levels_cancels_trade():
    df = ohlc([(100, 100, 100, 100), (112, 113, 111, 112)])
    assert simulate_trade(df, 0, True, 110, 95, NO_COSTS, False) is None


def test_short_trade_profits_from_a_fall():
    df = ohlc([(100, 100, 100, 100), (100, 101, 99, 100), (95, 96, 89, 90)])
    t = simulate_trade(df, 0, False, take_profit=90, stop_loss=105, costs=NO_COSTS, french_equity=False)
    assert t["outcome"] == "objectif"
    assert t["gross_return"] == pytest.approx(0.10)


def test_costs_include_ftt_only_for_french_equities():
    costs = Costs(commission=0.001, slippage=0.0005, ftt=0.004)
    assert costs.round_trip(True, french_equity=False) == pytest.approx(0.003)
    assert costs.round_trip(True, french_equity=True) == pytest.approx(0.007)
    df = ohlc([(100, 100, 100, 100), (100, 111, 99, 110)])
    t = simulate_trade(df, 0, True, 110, 95, costs, french_equity=True)
    assert t["net_return"] == pytest.approx(0.10 - 0.007)
    assert t["r_multiple"] == pytest.approx((0.10 - 0.007) / 0.05)


def test_same_pattern_does_not_stack_while_a_trade_is_open():
    rows = [(100, 100, 100, 100)] + [(100, 101, 99, 100)] * 10
    df = ohlc(rows)
    signals = pd.DataFrame(
        {
            "signal_pos": [0, 1, 2, 1],
            "signal_date": [df.index[i] for i in (0, 1, 2, 1)],
            "pattern_type": ["Bull Flag", "Bull Flag", "Bull Flag", "Double Bottom"],
            "bullish": [True, True, True, True],
            "confidence": [60.0] * 4,
            "take_profit": [120.0] * 4,
            "stop_loss": [90.0] * 4,
        }
    )
    trades = run_trades("X.PA", df, signals, NO_COSTS, False, max_hold=5)
    kinds = sorted(t.pattern_type for t in trades)
    assert kinds == ["Bull Flag", "Double Bottom"]  # les 2 Bull Flag suivants tombent pendant le 1er trade


def test_generate_signals_only_sees_the_past(monkeypatch):
    # Faux détecteur qui signale à chaque séance : on vérifie qu'il ne voit
    # jamais plus loin que la séance de signal, et qu'aucun signal ne tombe
    # sur la dernière séance (pas de lendemain pour entrer).
    from engine import backtest_detectors as bd
    from engine.patterns.common import PatternMatch

    seen_last = []

    def fake_detect_all(sub):
        seen_last.append(sub.index[-1])
        assert len(sub) == 50
        return [PatternMatch("Bull Flag", sub.index[-1], 60.0, {})]

    monkeypatch.setattr(bd, "detect_all", fake_detect_all)
    monkeypatch.setattr(bd, "propose_levels", lambda pt, ctx, entry, sub: (entry * 1.1, entry * 0.95))
    df = ohlc([(100 + i, 101 + i, 99 + i, 100 + i) for i in range(60)])

    signals = generate_signals(df, window=50)

    assert list(signals["signal_pos"]) == list(range(49, 59))
    assert seen_last == list(df.index[49:59])
    for row in signals.itertuples():
        assert row.signal_date == df.index[row.signal_pos]
        assert row.take_profit == pytest.approx(df["close"].iloc[row.signal_pos] * 1.1)


def test_open_trade_at_end_of_data_is_not_counted():
    rows = [(100, 100, 100, 100)] + [(100, 102, 98, 101)] * 3
    assert simulate_trade(ohlc(rows), 0, True, 120, 90, NO_COSTS, False, max_hold=10) is None


def test_trades_follow_signal_dates_when_price_history_is_refreshed():
    # Le cache de prix retéléchargé commence 2 séances plus tard : les
    # positions stockées sont périmées, la date doit faire foi.
    rows = [(100, 100, 100, 100)] * 2 + [(100, 100, 100, 100), (100, 111, 99, 110)] + [(110, 110, 110, 110)] * 3
    full = ohlc(rows)
    signal_date = full.index[2]
    refreshed = full.iloc[2:]
    signals = pd.DataFrame(
        {
            "signal_pos": [2],  # position dans l'ancien historique
            "signal_date": [signal_date],
            "pattern_type": ["Bull Flag"],
            "bullish": [True],
            "confidence": [60.0],
            "take_profit": [110.0],
            "stop_loss": [95.0],
        }
    )
    trades = run_trades("X.PA", refreshed, signals, NO_COSTS, False, max_hold=3)
    assert len(trades) == 1
    assert trades[0].entry_date == full.index[3]
    assert trades[0].outcome == "objectif"


def test_expectancy_r_is_not_blown_up_by_a_tiny_stop():
    trades = pd.DataFrame(
        {
            "net_return": [0.02, -0.01, -0.01],
            "risk": [0.02, 0.02, 0.0001],  # un stop à 0,01 % de l'entrée
            "r_multiple": [1.0, -0.5, -100.0],
            "bars_held": [3, 2, 1],
        }
    )
    s = summarize(trades)
    assert s["esperance_R"] == pytest.approx(0.0)  # moyenne nette nulle → espérance nulle


def test_verdict_requires_beating_random_entries():
    stats = {"trades": 200, "net_moyen_pct": 0.3, "t_stat": 2.5}
    halves = ({"net_moyen_pct": 0.2}, {"net_moyen_pct": 0.4})
    assert verdict(stats, *halves, hurdle_pct=0.0) == "avantage"
    assert verdict(stats, *halves, hurdle_pct=0.5) == "incertain"


def test_baseline_counts_every_tradable_session():
    rows = [(100, 101, 99, 100)] * 320
    b = baseline_returns(ohlc(rows), NO_COSTS, False, hold=10)
    assert b["n"] == 320 - 300 - 10 + 1
    assert b["long_sum"] == pytest.approx(0.0)


def test_summarize_and_verdict():
    trades = pd.DataFrame({"net_return": [0.02, -0.01, 0.03, -0.01], "r_multiple": [1, -0.5, 1.5, -0.5], "bars_held": [3, 2, 5, 2]})
    s = summarize(trades)
    assert s["trades"] == 4
    assert s["reussite_pct"] == 50
    assert s["profit_factor"] == pytest.approx(0.05 / 0.02)
    assert summarize(trades.iloc[:0]) == {"trades": 0}

    good = {"trades": 100, "net_moyen_pct": 0.5, "t_stat": 2.5}
    assert verdict(good, {"net_moyen_pct": 0.4}, {"net_moyen_pct": 0.6}) == "avantage"
    assert verdict(good, {"net_moyen_pct": 0.4}, {"net_moyen_pct": -0.1}) == "incertain"
    bad = {"trades": 100, "net_moyen_pct": -0.5, "t_stat": -3}
    assert verdict(bad, {"net_moyen_pct": -0.4}, {"net_moyen_pct": -0.6}) == "à écarter"
    assert verdict({"trades": 5}, {}, {}) == "trop peu de trades"
    assert math.isnan(summarize(trades.iloc[:1])["t_stat"])
