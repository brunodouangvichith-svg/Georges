"""Tests purs (aucune DB, aucun réseau) du module de validation (Phase 7,
MVP, `agents/orchestrator/validation.py`). C'est le test explicitement
demandé par la roadmap (tâche 7) : des sources contradictoires doivent
finir en quarantaine, pas être intégrées."""

from agents.orchestrator.types import CollectedItem
from agents.orchestrator.validation import SINGLE_SOURCE_RELIABILITY, validate


def _item(value, source_name="FRED", observed_at="2026-07-27", unit=None, symbol=None):
    return CollectedItem(
        label="Taux de change EUR/USD",
        value=value,
        unit=unit,
        source_name=source_name,
        source_url="https://example.test",
        observed_at=observed_at,
        symbol=symbol,
    )


def test_single_source_is_validated_with_moderate_reliability():
    outcome = validate("Taux OAT 10 ans (France)", [_item(3.68, source_name="FRED")])
    assert outcome.status == "validated"
    assert outcome.reliability_score == SINGLE_SOURCE_RELIABILITY
    assert "3.68" in outcome.description
    assert "unique" in outcome.reason.lower()


def test_two_agreeing_sources_are_validated_with_higher_reliability():
    outcome = validate(
        "Taux de change EUR/USD",
        [_item(1.1385, source_name="FRED"), _item(1.1377, source_name="BCE")],
    )
    assert outcome.status == "validated"
    assert outcome.reliability_score > SINGLE_SOURCE_RELIABILITY
    assert len(outcome.payload["sources"]) == 2


def test_two_contradictory_sources_are_quarantined_not_integrated():
    outcome = validate(
        "Taux de change EUR/USD",
        [_item(1.10, source_name="FRED"), _item(1.30, source_name="BCE")],
        tolerance_pct=1.0,
    )
    assert outcome.status == "quarantine"
    assert "FRED" in outcome.reason and "BCE" in outcome.reason
    assert "1.1" in outcome.reason and "1.3" in outcome.reason


def test_validate_without_any_item_raises():
    import pytest

    with pytest.raises(ValueError):
        validate("Taux OAT 10 ans (France)", [])


def test_symbol_and_unit_survive_into_the_outcome():
    outcome = validate("Taux OAT 10 ans (France)", [_item(3.68, unit="%", symbol="AIR.PA")])
    assert outcome.symbol == "AIR.PA"
    assert outcome.payload["sources"][0]["unit"] == "%"
