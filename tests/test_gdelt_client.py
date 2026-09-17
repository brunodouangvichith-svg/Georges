"""Tests de `agents/gdelt_client.py` — réseau entièrement mocké, même
discipline que `tests/test_eurostat.py`/`tests/test_worldbank.py`. La forme
`{"articles": [...]}` reproduit la forme réelle documentée par la Doc API
GDELT v2 (mode `ArtList`, déjà vérifiée en production dans
`clients/gdelt_client.py` du projet sœur dont ce module est porté)."""

from agents import gdelt_client


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_articles_returns_title_and_url_with_empty_extrait(monkeypatch):
    """La Doc API GDELT ne renvoie pas de texte de page (voir docstring du
    module) -- `extrait` doit rester vide plutôt qu'inventé."""
    payload = {
        "articles": [
            {"title": "Drone strike hits oil facility near Isfahan", "url": "https://example.com/a", "sourcecountry": "Iran"},
            {"title": "Protests continue in Tehran", "url": "https://example.com/b", "sourcecountry": "Iran"},
        ]
    }
    monkeypatch.setattr(gdelt_client.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    results = gdelt_client.search_articles("Iran")
    assert len(results) == 2
    assert results[0] == {"titre": "Drone strike hits oil facility near Isfahan", "extrait": "", "url": "https://example.com/a"}


def test_search_articles_skips_entries_without_a_url(monkeypatch):
    payload = {"articles": [{"title": "Sans URL"}, {"title": "Avec URL", "url": "https://example.com/c"}]}
    monkeypatch.setattr(gdelt_client.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(payload))

    results = gdelt_client.search_articles("France")
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/c"


def test_search_articles_returns_empty_list_on_network_failure(monkeypatch):
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(gdelt_client.requests, "get", _raise)
    assert gdelt_client.search_articles("France") == []


def test_search_articles_returns_empty_list_when_no_articles_key(monkeypatch):
    monkeypatch.setattr(gdelt_client.requests, "get", lambda url, params=None, timeout=None: _FakeResponse({}))
    assert gdelt_client.search_articles("France") == []


def test_search_articles_retries_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}
    payload = {"articles": [{"title": "OK", "url": "https://example.com/d"}]}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse({}, status_code=429)
        return _FakeResponse(payload)

    monkeypatch.setattr(gdelt_client.requests, "get", fake_get)
    monkeypatch.setattr(gdelt_client.time, "sleep", lambda seconds: None)  # pas de vraie pause dans les tests

    results = gdelt_client.search_articles("France")
    assert calls["n"] == 2
    assert len(results) == 1


def test_search_articles_gives_up_after_max_retries_on_persistent_429(monkeypatch):
    monkeypatch.setattr(gdelt_client.requests, "get", lambda url, params=None, timeout=None: _FakeResponse({}, status_code=429))
    monkeypatch.setattr(gdelt_client.time, "sleep", lambda seconds: None)

    assert gdelt_client.search_articles("France") == []


def test_search_articles_query_includes_country_and_is_anded_with_keywords(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params)
        return _FakeResponse({"articles": []})

    monkeypatch.setattr(gdelt_client.requests, "get", fake_get)
    gdelt_client.search_articles("Iran")

    assert '"Iran"' in captured["query"]
    assert "oil" in captured["query"]
    assert captured["mode"] == "ArtList"


def test_search_articles_translates_french_country_name_for_the_query(monkeypatch):
    """GDELT est restreint à `sourcelang: english` -- un nom de pays français
    tel quel (ex. "Allemagne") ne matcherait quasiment aucun article. Le
    terme de requête doit donc utiliser l'équivalent anglais du mapping
    `GDELT_COUNTRY_NAMES`, jamais le nom français brut."""
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params)
        return _FakeResponse({"articles": []})

    monkeypatch.setattr(gdelt_client.requests, "get", fake_get)
    gdelt_client.search_articles("Allemagne")

    assert '"Germany"' in captured["query"]
    assert "Allemagne" not in captured["query"]


def test_search_articles_falls_back_to_raw_name_when_not_in_mapping(monkeypatch):
    """Un pays absent de `GDELT_COUNTRY_NAMES` (hors des 77 de la whitelist)
    ne doit jamais faire échouer la recherche -- repli tolérant sur le nom
    tel quel, même éthique que le reste du projet."""
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params)
        return _FakeResponse({"articles": []})

    monkeypatch.setattr(gdelt_client.requests, "get", fake_get)
    gdelt_client.search_articles("Andorre")

    assert '"Andorre"' in captured["query"]
