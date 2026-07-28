"""Tests des sous-agents de collecte (Phase 7, MVP, `agents/collectors/`) —
réseau et LLM entièrement mockés, comme `tests/test_agents.py`/`test_api.py`
le font déjà pour `mistral_client`."""

import datetime

import pytest

import agents.mistral_client as mistral_client
from agents.collectors import macro, synthesis
from ingestion.models import Report

FRED_CSV = "observation_date,IRLTLT01FRM156N\n2026-06-01,3.68\n2026-07-01,.\n"
ECB_CSV = (
    "KEY,FREQ,TIME_PERIOD,OBS_VALUE,TITLE_COMPL\n"
    'EXR.D.USD.EUR.SP00.A,D,2026-07-27,1.1389,"ECB reference exchange rate, US dollar/Euro"\n'
)


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeDB:
    def __init__(self, report=None):
        self._report = report

    def get(self, model, report_id):
        return self._report if self._report is not None and self._report.id == report_id else None


def _report(report_id=1, content="George Index moyen : 62. AIR.PA en figure Bull Flag, confiance 77%."):
    report = Report(scope="basket:1", basket_id=1, content=content, embedding=[0.0] * 1024)
    report.id = report_id
    report.created_at = datetime.datetime(2026, 7, 27, tzinfo=datetime.timezone.utc)
    return report


def test_fetch_fred_series_skips_missing_observations_and_returns_the_latest_real_value(monkeypatch):
    monkeypatch.setattr(macro.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV))
    item = macro.fetch_fred_series("IRLTLT01FRM156N", label="Taux OAT 10 ans (France)", source_name="FRED", unit="%")
    assert item is not None
    assert item.value == 3.68  # la ligne "." (manquante) est ignorée
    assert item.observed_at == "2026-06-01"
    assert item.source_name == "FRED"


def test_fetch_fred_series_returns_none_on_network_failure(monkeypatch):
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(macro.requests, "get", _raise)
    assert macro.fetch_fred_series("IRLTLT01FRM156N", label="x", source_name="FRED", unit="%") is None


def test_fetch_ecb_series_parses_the_real_csvdata_shape(monkeypatch):
    monkeypatch.setattr(macro.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(ECB_CSV))
    item = macro.fetch_ecb_series("D.USD.EUR.SP00.A", label="Taux de change EUR/USD", source_name="BCE", unit=None)
    assert item is not None
    assert item.value == 1.1389
    assert item.observed_at == "2026-07-27"


def test_collect_donnees_macro_groups_by_indicator(monkeypatch):
    # Le nom de la colonne valeur est celui de la série demandée (vérifié
    # contre l'API réelle) — la réponse canned doit donc varier avec `id`,
    # pas être un unique CSV statique partagé par toutes les séries.
    def fake_get(url, params=None, timeout=None):
        return _FakeResponse(f"observation_date,{params['id']}\n2026-06-01,3.68\n")

    monkeypatch.setattr(macro.requests, "get", fake_get)
    monkeypatch.setattr(macro, "fetch_ecb_series", lambda *a, **k: None)  # BCE indisponible ce cycle

    groups = macro.collect_donnees_macro(db=None, engine=None)
    labels = {label: len(items) for label, items in groups}
    assert labels["Taux OAT 10 ans (France)"] == 1
    # EUR/USD ne garde que la source FRED (BCE en échec) — toujours inclus, pas de groupe vide.
    assert labels["Taux de change EUR/USD"] == 1


def test_collect_synthese_document_sends_the_real_report_content_to_the_prompt(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, user_message, model=None):
        captured["user_message"] = user_message
        return "- George Index moyen à 62.\n- AIR.PA en Bull Flag, confiance 77%."

    monkeypatch.setattr(mistral_client, "complete", fake_complete)
    report = _report()
    groups = synthesis.collect_synthese_document(_FakeDB(report), engine=None, scope={"report_id": report.id})

    assert len(groups) == 1
    label, items = groups[0]
    assert len(items) == 1
    assert "George Index moyen : 62" in captured["user_message"]  # vraie donnée du rapport, pas fabriquée
    assert items[0].value == "- George Index moyen à 62.\n- AIR.PA en Bull Flag, confiance 77%."
    assert items[0].source_name == "Rapport interne"


def test_collect_synthese_document_without_report_id_raises():
    with pytest.raises(ValueError):
        synthesis.collect_synthese_document(_FakeDB(), engine=None, scope=None)


def test_collect_synthese_document_unknown_report_raises():
    with pytest.raises(ValueError):
        synthesis.collect_synthese_document(_FakeDB(report=None), engine=None, scope={"report_id": 999})
