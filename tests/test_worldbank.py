"""Tests du sous-agent de collecte World Bank (`agents/collectors/worldbank.py`)
— réseau entièrement mocké, même discipline que `tests/test_eurostat.py`.
La forme `[métadonnées, données]` reproduit la forme réelle documentée par
l'API World Bank v2, déjà vérifiée en production dans
`clients/worldbank_client.py` du projet sœur dont ce module est porté."""

from agents.collectors import worldbank


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _worldbank_payload(entries):
    return [{"page": 1, "pages": 1, "per_page": 20, "total": len(entries)}, entries]


def test_fetch_worldbank_indicator_picks_the_most_recent_value_regardless_of_response_order(monkeypatch):
    """L'ordre de la réponse n'est pas supposé trié -- ici volontairement
    mélangé pour vérifier que le tri par date se fait bien côté client,
    pas juste `entries[0]`."""
    payload = _worldbank_payload(
        [
            {"countryiso3code": "FRA", "date": "2022", "value": 7.3},
            {"countryiso3code": "FRA", "date": "2024", "value": 7.1},
            {"countryiso3code": "FRA", "date": "2023", "value": 7.2},
        ]
    )
    monkeypatch.setattr(worldbank.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    item = worldbank.fetch_worldbank_indicator(
        "SL.UEM.TOTL.ZS", "FRA", label="Taux de chômage (France, Banque mondiale)", source_name="Banque mondiale", unit="%"
    )
    assert item is not None
    assert item.value == 7.1
    assert item.observed_at == "2024"
    assert item.source_name == "Banque mondiale"


def test_fetch_worldbank_indicator_requests_a_date_range_relative_to_the_current_year(monkeypatch):
    """Régression `/code-review` : une première version figeait la fenêtre
    sur "2015:2025" en dur, qui aurait cessé de voir toute nouvelle
    publication une fois 2025 passé -- doit être calculée à chaque appel."""
    captured_params = {}

    def fake_get(url, params=None, timeout=None):
        captured_params.update(params)
        return _FakeResponse(_worldbank_payload([{"countryiso3code": "FRA", "date": "2024", "value": 1.0}]))

    monkeypatch.setattr(worldbank.requests, "get", fake_get)
    worldbank.fetch_worldbank_indicator("SL.UEM.TOTL.ZS", "FRA", label="x", source_name="Banque mondiale", unit="%")

    import datetime

    current_year = datetime.datetime.now(datetime.timezone.utc).year
    assert captured_params["date"] == f"{current_year - worldbank.YEARS_OF_HISTORY}:{current_year}"


def test_fetch_worldbank_indicator_skips_null_values_and_scans_back(monkeypatch):
    """La dernière année publiée peut ne pas encore avoir de valeur (null)
    -- doit remonter à la plus récente valeur réellement présente."""
    payload = _worldbank_payload(
        [
            {"countryiso3code": "FRA", "date": "2025", "value": None},
            {"countryiso3code": "FRA", "date": "2024", "value": 2.3},
        ]
    )
    monkeypatch.setattr(worldbank.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    item = worldbank.fetch_worldbank_indicator(
        "FP.CPI.TOTL.ZG", "FRA", label="Inflation (France, Banque mondiale)", source_name="Banque mondiale", unit="%"
    )
    assert item is not None
    assert item.value == 2.3
    assert item.observed_at == "2024"


def test_fetch_worldbank_indicator_returns_none_when_no_numeric_observation(monkeypatch):
    payload = _worldbank_payload([{"countryiso3code": "FRA", "date": "2025", "value": None}])
    monkeypatch.setattr(worldbank.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    item = worldbank.fetch_worldbank_indicator("MS.MIL.XPND.GD.ZS", "FRA", label="x", source_name="Banque mondiale", unit="%")
    assert item is None


def test_fetch_worldbank_indicator_returns_none_on_unexpected_payload_shape(monkeypatch):
    monkeypatch.setattr(
        worldbank.requests, "get", lambda url, params=None, timeout=None: _FakeResponse({"message": "invalid indicator"})
    )

    item = worldbank.fetch_worldbank_indicator("BOGUS", "FRA", label="x", source_name="Banque mondiale", unit="%")
    assert item is None


def test_fetch_worldbank_indicator_returns_none_on_network_failure(monkeypatch):
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(worldbank.requests, "get", _raise)
    assert worldbank.fetch_worldbank_indicator("SL.UEM.TOTL.ZS", "FRA", label="x", source_name="Banque mondiale", unit="%") is None


def test_collect_donnees_worldbank_skips_indicator_on_failure(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(indicator_code, country, label, source_name, unit):
        calls["n"] += 1
        if indicator_code == "SL.UEM.TOTL.ZS":
            return worldbank.CollectedItem(
                label=label, value=7.1, unit=unit, source_name=source_name, source_url="x", observed_at="2024"
            )
        return None  # les autres indicateurs indisponibles ce cycle

    monkeypatch.setattr(worldbank, "fetch_worldbank_indicator", fake_fetch)
    groups = worldbank.collect_donnees_worldbank(db=None, engine=None)
    labels = {label: len(items) for label, items in groups}
    assert labels == {"Taux de chômage (France, Banque mondiale)": 1}
    assert calls["n"] == len(worldbank.INDICATORS)
