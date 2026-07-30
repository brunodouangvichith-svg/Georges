"""Tests du sous-agent de collecte Eurostat (`agents/collectors/eurostat.py`)
— réseau entièrement mocké, même discipline que `tests/test_collectors.py`.
Les fixtures JSON-stat reproduisent la forme réelle vérifiée en direct
contre `ec.europa.eu/eurostat/api/dissemination/...` (geo précède time dans
`id`, `value` est un dict creux clé->valeur)."""

from agents.collectors import eurostat


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _jsonstat_payload(geo_index_map, time_index_map, values, geo_size, time_size):
    return {
        "id": ["freq", "s_adj", "age", "unit", "sex", "geo", "time"],
        "size": [1, 1, 1, 1, 1, geo_size, time_size],
        "dimension": {
            "geo": {"category": {"index": geo_index_map}},
            "time": {"category": {"index": time_index_map}},
        },
        "value": values,
    }


def test_fetch_eurostat_series_finds_geo_and_scans_back_for_latest_present_value(monkeypatch):
    # geo EA21 est à l'index 1 sur 3 catégories géo ; time a 4 périodes
    # (index 0..3) — la période la plus récente (offset 7) est absente
    # (mois pas encore publié), la fonction doit remonter jusqu'à l'offset 6.
    payload = _jsonstat_payload(
        geo_index_map={"BE": 0, "EA21": 1, "FR": 2},
        time_index_map={"2026-03": 0, "2026-04": 1, "2026-05": 2, "2026-06": 3},
        values={"4": 6.4, "5": 6.3, "6": 6.2},
        geo_size=3,
        time_size=4,
    )
    monkeypatch.setattr(eurostat.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    item = eurostat.fetch_eurostat_series(
        "une_rt_m", "EA21", {"s_adj": "SA"}, label="Taux de chômage (zone euro)", source_name="Eurostat", unit="%"
    )
    assert item is not None
    assert item.value == 6.2
    assert item.observed_at == "2026-05"
    assert item.source_name == "Eurostat"


def test_fetch_eurostat_series_returns_none_when_geo_code_unknown(monkeypatch):
    payload = _jsonstat_payload(
        geo_index_map={"BE": 0, "FR": 1},  # EA20 absent — code géo invalide pour ce dataset
        time_index_map={"2026-06": 0},
        values={"0": 2.0, "1": 2.1},
        geo_size=2,
        time_size=1,
    )
    monkeypatch.setattr(eurostat.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    item = eurostat.fetch_eurostat_series(
        "prc_hicp_manr", "EA20", {"unit": "RCH_A"}, label="Inflation HICP (zone euro)", source_name="Eurostat", unit="%"
    )
    assert item is None


def test_fetch_eurostat_series_returns_none_on_network_failure(monkeypatch):
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(eurostat.requests, "get", _raise)
    assert eurostat.fetch_eurostat_series("une_rt_m", "EA21", {}, label="x", source_name="Eurostat", unit="%") is None


def test_collect_donnees_eurostat_skips_indicator_on_failure(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(dataset, geo_code, params, label, source_name, unit):
        calls["n"] += 1
        if dataset == "une_rt_m":
            return eurostat.CollectedItem(
                label=label, value=6.2, unit=unit, source_name=source_name, source_url="x", observed_at="2026-05"
            )
        return None  # HICP indisponible ce cycle

    monkeypatch.setattr(eurostat, "fetch_eurostat_series", fake_fetch)
    groups = eurostat.collect_donnees_eurostat(db=None, engine=None)
    labels = {label: len(items) for label, items in groups}
    assert labels == {"Taux de chômage (zone euro)": 1}
    assert calls["n"] == 2
