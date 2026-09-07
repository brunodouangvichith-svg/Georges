"""Tests de `agents/web_search.py` — pur, sans DB, sans réseau : `httpx.post`
est monkeypatché, comme `tests/test_mistral_client.py` pour le repli
DeepSeek."""
import agents.web_search as web_search


class _FakeTavilyResponse:
    def __init__(self, results):
        self._results = results

    def raise_for_status(self):
        pass

    def json(self):
        return {"results": self._results}


def test_search_returns_empty_list_when_no_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Tavily ne doit pas être appelé sans TAVILY_API_KEY")

    monkeypatch.setattr(web_search.httpx, "post", fail_if_called)

    assert web_search.search("question quelconque") == []


def test_search_shapes_tavily_results(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["query"] = json["query"]
        captured["api_key"] = json["api_key"]
        return _FakeTavilyResponse(
            [{"title": "MACD (Investopedia)", "content": "Moving average...", "url": "https://example.com/macd"}]
        )

    monkeypatch.setattr(web_search.httpx, "post", fake_post)

    results = web_search.search("Qu'est-ce que le MACD ?")

    assert captured["url"] == web_search.TAVILY_API_URL
    assert captured["query"] == "Qu'est-ce que le MACD ?"
    assert captured["api_key"] == "tvly-test"
    assert results == [
        {"titre": "MACD (Investopedia)", "extrait": "Moving average...", "url": "https://example.com/macd"}
    ]


def test_search_raises_web_search_unavailable_on_http_failure(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    def fake_post(*args, **kwargs):
        raise RuntimeError("Tavily injoignable")

    monkeypatch.setattr(web_search.httpx, "post", fake_post)

    try:
        web_search.search("question")
        assert False, "devait lever WebSearchUnavailableError"
    except web_search.WebSearchUnavailableError as err:
        assert "Tavily injoignable" in str(err)


def test_search_handles_missing_fields_gracefully(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(
        web_search.httpx, "post", lambda *a, **k: _FakeTavilyResponse([{"url": "https://example.com/no-title"}])
    )

    results = web_search.search("question")

    assert results == [{"titre": "", "extrait": "", "url": "https://example.com/no-title"}]
