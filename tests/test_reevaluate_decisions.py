"""Teste `engine/reevaluate_decisions.py:evaluate_decision` — pur, sur des
DataFrames synthétiques, pas d'accès DB (le script `run()` qui lit/écrit en
base n'est pas couvert ici, comme pour `engine/build_training_set.py`)."""
import types

import pandas as pd

from engine.reevaluate_decisions import evaluate_decision
from tests.test_patterns import make_df


def _decision(decision_type="Achat", entry_price=100.0, take_profit=110.0, stop_loss=95.0, created_at=None):
    return types.SimpleNamespace(
        decision_type=decision_type,
        entry_price=entry_price,
        take_profit=take_profit,
        stop_loss=stop_loss,
        created_at=created_at or pd.Timestamp("2023-01-02"),
    )


def test_take_profit_hit_for_bullish_decision():
    df = make_df([100, 102, 104, 106, 108, 111, 109])
    result, pnl_pct, hit_at = evaluate_decision(_decision(), df)
    assert result == "take_profit_hit"
    assert pnl_pct == 10.0
    assert hit_at is not None


def test_stop_loss_hit_for_bullish_decision():
    df = make_df([100, 99, 98, 97, 96, 94, 96])
    result, pnl_pct, hit_at = evaluate_decision(_decision(), df)
    assert result == "stop_loss_hit"
    assert pnl_pct == -5.0
    assert hit_at is not None


def test_still_open_when_no_level_touched():
    df = make_df([100, 101, 100.5, 102, 101.5])
    result, pnl_pct, hit_at = evaluate_decision(_decision(), df)
    assert result == "open"
    assert hit_at is None


def test_bearish_decision_take_profit_is_a_price_drop():
    decision = _decision(decision_type="Alléger", entry_price=100.0, take_profit=90.0, stop_loss=105.0)
    df = make_df([100, 98, 96, 94, 91, 89, 92])
    result, pnl_pct, hit_at = evaluate_decision(decision, df)
    assert result == "take_profit_hit"
    assert pnl_pct == 10.0  # gain pour une position "Alléger" quand le prix baisse


def test_none_when_no_session_since_creation():
    decision = _decision(created_at=pd.Timestamp("2099-01-01"))
    df = make_df([100, 101, 102])
    assert evaluate_decision(decision, df) is None
