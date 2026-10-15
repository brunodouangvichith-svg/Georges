"""Tests de `engine/bond_bulletin.py:generate_daily_bulletin` -- DB mockée
(résumé et alertes injectés directement), même principe que les tests
`agents/jane*` de ce projet pour les fonctions qui combinent plusieurs
sources déjà calculées. Vérifie la consigne explicite du cahier des
charges : distinguer FAITS VÉRIFIÉS / INTERPRÉTATION / CONSÉQUENCES
POSSIBLES, et ne jamais affirmer qu'une hausse de l'OAT entraîne
mécaniquement une hausse identique des taux immobiliers."""

import engine.bond_bulletin as bond_bulletin
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_UST_US_10Y,
    BOND_INSTRUMENT_UST_US_2Y,
)


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)


class _FakeDB:
    """Exécute `select(BondAlertEvent)...` sans toucher à une vraie DB --
    `_recent_alerts_section` n'a besoin que de `db.execute(...).scalars().all()`."""

    def __init__(self, alert_events):
        self._alert_events = alert_events

    def execute(self, _stmt):
        return _FakeResult(self._alert_events)


def _full_card(instrument, value_pct, variations=None):
    return {
        "instrument": instrument,
        "value_pct": value_pct,
        "observed_at": "2026-10-13",
        "fetched_at": "2026-10-14T06:00:00+00:00",
        "source_name": "FRED",
        "source_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=X",
        "variations_bps": variations or {"24h": None, "7j": None, "30j": 10.0},
    }


def _missing_card(instrument):
    return {
        "instrument": instrument,
        "value_pct": None,
        "observed_at": None,
        "fetched_at": None,
        "source_name": None,
        "source_url": None,
        "variations_bps": {"24h": None, "7j": None, "30j": None},
    }


def _summary(spread=120.0, curve=50.0):
    return {
        "cards": [
            _full_card(BOND_INSTRUMENT_OAT_FR_10Y, 4.00),
            _full_card(BOND_INSTRUMENT_BUND_DE_10Y, 2.80),
            _full_card(BOND_INSTRUMENT_UST_US_10Y, 4.50),
            _full_card(BOND_INSTRUMENT_UST_US_2Y, 4.00),
        ],
        "spread_oat_bund_bps": spread,
        "us_curve_slope_bps": curve,
    }


def test_bulletin_has_the_three_required_sections(monkeypatch):
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary())
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "=== FAITS VÉRIFIÉS ===" in text
    assert "=== INTERPRÉTATION ===" in text
    assert "=== CONSÉQUENCES POSSIBLES ===" in text


def test_bulletin_cites_real_numbers_not_invented_ones(monkeypatch):
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary(spread=120.0, curve=50.0))
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "4.00%" in text
    assert "2.80%" in text
    assert "+120" in text
    assert "+50" in text


def test_bulletin_never_claims_a_mechanical_link_between_oat_and_mortgage_rates(monkeypatch):
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary())
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "ne suivent PAS mécaniquement" in text
    assert "taux de swap" in text


def test_bulletin_lists_unavailable_instruments_explicitly(monkeypatch):
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary())
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "Swap EUR 10 ans : non disponible." in text
    assert "OAT France 2 ans : non disponible." in text


def test_bulletin_handles_missing_data_without_fabricating_values(monkeypatch):
    summary = {
        "cards": [
            _missing_card(BOND_INSTRUMENT_OAT_FR_10Y),
            _missing_card(BOND_INSTRUMENT_BUND_DE_10Y),
            _missing_card(BOND_INSTRUMENT_UST_US_10Y),
            _missing_card(BOND_INSTRUMENT_UST_US_2Y),
        ],
        "spread_oat_bund_bps": None,
        "us_curve_slope_bps": None,
    }
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: summary)
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "donnée indisponible" in text
    assert "non calculable" in text


def test_bulletin_reports_no_active_alerts_when_none(monkeypatch):
    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary())
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([]))
    assert "Aucun seuil d'alerte actuellement franchi." in text


def test_bulletin_lists_active_alerts_with_their_message(monkeypatch):
    class _FakeEvent:
        message = "OAT_FR_10Y a dépassé 4.9% (valeur actuelle : 5.1%)."

        class triggered_at:
            @staticmethod
            def date():
                import datetime

                return datetime.date(2026, 10, 10)

    monkeypatch.setattr(bond_bulletin, "build_dashboard_summary", lambda db: _summary())
    text = bond_bulletin.generate_daily_bulletin(_FakeDB([_FakeEvent()]))
    assert "OAT_FR_10Y a dépassé 4.9%" in text
