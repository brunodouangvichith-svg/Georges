"""`engine/virtual_portfolio.py` — pur, aucune base ni réseau."""

import pytest

from engine import virtual_portfolio as vp


def _trade(symbol, side, quantity, price):
    return {"symbol": symbol, "side": side, "quantity": quantity, "price": price, "fees": vp.fee_for(quantity * price)}


def test_holdings_start_from_initial_capital():
    h = vp.holdings_from_trades([])
    assert h.cash == vp.INITIAL_CAPITAL and h.positions == {} and h.fees_total == 0


def test_holdings_replay_buys_and_sells_with_fees():
    trades = [_trade("AIR.PA", "achat", 10, 200.0), _trade("AIR.PA", "vente", 10, 210.0)]
    h = vp.holdings_from_trades(trades)
    assert h.positions == {}
    assert h.fees_total == pytest.approx(3.0 + 3.15)
    assert h.cash == pytest.approx(100_000 - 2000 - 3.0 + 2100 - 3.15)


def test_unknown_side_is_rejected():
    with pytest.raises(ValueError):
        vp.holdings_from_trades([{"symbol": "X", "side": "short", "quantity": 1, "price": 1, "fees": 0}])


def test_positions_value_is_none_when_a_price_is_missing():
    assert vp.positions_value({"A": 2, "B": 1}, {"A": 10.0}) is None
    assert vp.positions_value({"A": 2}, {"A": 10.0}) == 20.0


def test_plan_buys_bullish_signals_by_confidence_and_keeps_cash_reserve():
    signals = {
        "A": vp.Signal("A", "Achat", 60),
        "B": vp.Signal("B", "Renforcer", 90),
        "C": vp.Signal("C", "Surveiller", 99),
        "D": vp.Signal("D", "Alléger", 99),
    }
    prices = {"A": 100.0, "B": 50.0, "C": 10.0, "D": 10.0}
    planned = vp.plan_trades(vp.Holdings(), signals, prices, "orange")
    assert [(t.symbol, t.side) for t in planned] == [("B", "achat"), ("A", "achat")]
    for trade in planned:
        assert trade.gross + trade.fees <= vp.TARGET_POSITION_WEIGHT * vp.INITIAL_CAPITAL + 1e-6
    spent = sum(t.gross + t.fees for t in planned)
    assert vp.INITIAL_CAPITAL - spent >= vp.MIN_CASH_BY_RISK["orange"] * vp.INITIAL_CAPITAL


def test_plan_never_breaches_the_cash_reserve():
    signals = {f"S{i}": vp.Signal(f"S{i}", "Achat", 80 - i) for i in range(20)}
    prices = {f"S{i}": 37.0 for i in range(20)}
    planned = vp.plan_trades(vp.Holdings(), signals, prices, "rouge")
    spent = sum(t.gross + t.fees for t in planned)
    assert vp.INITIAL_CAPITAL - spent >= vp.MIN_CASH_BY_RISK["rouge"] * vp.INITIAL_CAPITAL - 1e-6
    assert len(planned) <= vp.MAX_POSITIONS


def test_plan_sells_positions_whose_signal_turned_bearish_and_keeps_neutral_ones():
    holdings = vp.holdings_from_trades([_trade("A", "achat", 10, 100.0), _trade("B", "achat", 10, 100.0)])
    signals = {"A": vp.Signal("A", "Alléger", 70), "B": vp.Signal("B", "Surveiller", 70)}
    planned = vp.plan_trades(holdings, signals, {"A": 110.0, "B": 90.0}, "orange")
    assert [(t.symbol, t.side, t.quantity) for t in planned] == [("A", "vente", 10)]


def test_plan_does_not_rebuy_held_positions_or_trade_without_price():
    holdings = vp.holdings_from_trades([_trade("A", "achat", 10, 100.0)])
    signals = {"A": vp.Signal("A", "Achat", 90), "B": vp.Signal("B", "Achat", 80)}
    planned = vp.plan_trades(holdings, signals, {"A": 100.0}, "vert")
    assert planned == []


def test_plan_takes_no_new_risk_when_a_held_position_cannot_be_valued():
    holdings = vp.holdings_from_trades([_trade("A", "achat", 10, 100.0)])
    signals = {"B": vp.Signal("B", "Achat", 80)}
    assert vp.plan_trades(holdings, signals, {"B": 50.0}, "vert") == []
