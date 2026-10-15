"""Tests purs de `engine/performance.py` (aucune base, aucun réseau)."""

from datetime import datetime, timedelta, timezone

import pytest

from engine.performance import build_performance, latest_realised_outcomes, stats

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def row(decision_id, result, pnl, days=0, pattern="Double Bottom"):
    return {
        "decision_id": decision_id,
        "symbol": f"S{decision_id}.PA",
        "decision_type": "Achat",
        "entry_price": 100.0,
        "pattern_type": pattern,
        "result": result,
        "pnl_pct": pnl,
        "evaluated_at": T0 + timedelta(days=days),
        "closed_at": T0 + timedelta(days=days),
    }


def test_open_rows_are_never_counted_as_realised():
    rows = [row(1, "open", 12.0), row(2, "open", -4.0)]
    assert latest_realised_outcomes(rows) == []
    assert build_performance(rows)["summary"]["count"] == 0


def test_keeps_only_the_latest_realised_row_per_decision():
    rows = [row(1, "open", 3.0, days=0), row(1, "take_profit_hit", 8.0, days=2), row(1, "stop_loss_hit", -5.0, days=1)]
    trades = latest_realised_outcomes(rows)
    assert len(trades) == 1
    assert trades[0]["pnl_pct"] == 8.0


def test_stats_on_mixed_trades():
    trades = [row(1, "take_profit_hit", 10.0), row(2, "take_profit_hit", 6.0), row(3, "stop_loss_hit", -4.0), row(4, "stop_loss_hit", 0.0)]
    s = stats(trades)
    assert s["count"] == 4
    assert s["wins"] == 2 and s["losses"] == 1  # 0 % n'est ni un gain ni une perte
    assert s["win_rate_pct"] == 50.0
    assert s["avg_gain_pct"] == 8.0
    assert s["avg_loss_pct"] == -4.0
    assert s["total_pnl_pct"] == 12.0
    assert s["avg_pnl_pct"] == 3.0
    assert s["best_pnl_pct"] == 10.0 and s["worst_pnl_pct"] == -4.0


def test_empty_stats_are_null_not_zero():
    s = stats([])
    assert s["count"] == 0
    for key in ("win_rate_pct", "avg_pnl_pct", "avg_gain_pct", "avg_loss_pct", "total_pnl_pct"):
        assert s[key] is None


def test_only_losses_leaves_avg_gain_null():
    s = stats([row(1, "stop_loss_hit", -3.0)])
    assert s["avg_gain_pct"] is None
    assert s["avg_loss_pct"] == pytest.approx(-3.0)


def test_by_pattern_groups_and_labels_missing_patterns():
    rows = [
        row(1, "take_profit_hit", 5.0, pattern="Bull Flag"),
        row(2, "stop_loss_hit", -2.0, pattern="Bull Flag"),
        row(3, "take_profit_hit", 4.0, pattern=None),
    ]
    groups = {g["pattern_type"]: g for g in build_performance(rows)["by_pattern"]}
    assert groups["Bull Flag"]["count"] == 2
    assert groups["Bull Flag"]["win_rate_pct"] == 50.0
    assert groups["Sans figure"]["count"] == 1


def test_trades_are_sorted_newest_first():
    rows = [row(1, "take_profit_hit", 5.0, days=1), row(2, "stop_loss_hit", -2.0, days=5)]
    assert [t["decision_id"] for t in build_performance(rows)["trades"]] == [2, 1]
