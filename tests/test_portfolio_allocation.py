import pytest

from engine.portfolio_allocation import allocate_budget, format_allocation_summary


def _decision(decision_id, entry_price, stop_loss=None, take_profit=None, confidence=50.0, symbol=None):
    return {
        "decision_id": decision_id,
        "symbol": symbol or f"SYM{decision_id}.PA",
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "confidence": confidence,
    }


def test_allocate_budget_splits_proportionally_to_weight():
    # Même confiance, mais un bien meilleur ratio gain/risque pour A (10:1 vs 1:1)
    # -> A doit recevoir une part nettement plus grande du budget.
    decisions = [
        _decision(1, entry_price=100.0, stop_loss=99.0, take_profit=110.0, confidence=50.0),  # ratio 10
        _decision(2, entry_price=100.0, stop_loss=90.0, take_profit=110.0, confidence=50.0),  # ratio 1
    ]
    allocations = allocate_budget(decisions, budget=11_000.0)
    by_id = {a["decision_id"]: a for a in allocations}
    assert by_id[1]["quantity"] > by_id[2]["quantity"]


def test_allocate_budget_never_exceeds_budget():
    decisions = [_decision(1, entry_price=33.33, confidence=80), _decision(2, entry_price=17.5, confidence=40)]
    allocations = allocate_budget(decisions, budget=1000.0)
    assert sum(a["amount"] for a in allocations) <= 1000.0


def test_allocate_budget_uses_whole_shares_only():
    decisions = [_decision(1, entry_price=33.33, confidence=80)]
    allocations = allocate_budget(decisions, budget=1000.0)
    assert allocations[0]["quantity"] == int(allocations[0]["quantity"])
    assert allocations[0]["amount"] == pytest.approx(allocations[0]["quantity"] * 33.33, abs=0.01)


def test_allocate_budget_missing_levels_still_gets_a_share():
    # Pas de stop-loss/take-profit renseigné -> ratio neutre (1.0), mais pas
    # exclu de la répartition.
    decisions = [
        _decision(1, entry_price=100.0, confidence=50.0),
        _decision(2, entry_price=100.0, stop_loss=95.0, take_profit=120.0, confidence=50.0),
    ]
    allocations = allocate_budget(decisions, budget=10_000.0)
    assert all(a["quantity"] >= 0 for a in allocations)
    assert allocations[0]["quantity"] > 0


def test_allocate_budget_empty_or_non_positive_budget_returns_empty():
    assert allocate_budget([], budget=1000.0) == []
    assert allocate_budget([_decision(1, 100.0)], budget=0) == []
    assert allocate_budget([_decision(1, 100.0)], budget=-50) == []


def test_format_allocation_summary_cites_every_line_and_real_numbers():
    decisions = [_decision(1, 100.0, symbol="AAA.PA", confidence=80), _decision(2, 50.0, symbol="BBB.PA", confidence=60)]
    allocations = allocate_budget(decisions, budget=1000.0)
    summary = format_allocation_summary(decisions, allocations, budget=1000.0)
    assert "AAA.PA" in summary
    assert "BBB.PA" in summary
    assert "1,000.00" in summary  # montant total du budget cité
    for alloc in allocations:
        assert str(alloc["quantity"]) in summary
