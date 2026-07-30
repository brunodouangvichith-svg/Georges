"""Tests du sous-agent de collecte Finnhub (`agents/collectors/finnhub.py`)
— réseau entièrement mocké. **La forme JSON utilisée ici vient de la
documentation publique de Finnhub, pas d'un vrai appel authentifié**
(aucune clé `FINNHUB_API_KEY` disponible au moment de l'écriture) — à
corriger dès qu'une clé réelle est configurée."""

import pytest

from agents.collectors import finnhub


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_finnhub_quote_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert finnhub.fetch_finnhub_quote("TTE.PA", label="x", source_name="Finnhub", unit="€") is None


def test_fetch_finnhub_quote_parses_the_documented_json_shape(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(
        finnhub.requests,
        "get",
        lambda url, params=None, timeout=None: _FakeResponse(
            {"c": 63.42, "d": 0.5, "dp": 0.8, "h": 63.9, "l": 62.8, "o": 63.0, "pc": 62.92, "t": 1753776000}
        ),
    )
    item = finnhub.fetch_finnhub_quote("TTE.PA", label="Cotation Finnhub (TTE.PA)", source_name="Finnhub", unit="€")
    assert item is not None
    assert item.value == 63.42
    assert item.symbol == "TTE.PA"


def test_fetch_finnhub_quote_returns_none_when_price_is_zero(monkeypatch):
    # Finnhub renvoie c: 0 (pas d'erreur HTTP) pour un symbole inconnu/non
    # couvert par le palier gratuit — traité comme un échec de collecte.
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(
        finnhub.requests,
        "get",
        lambda url, params=None, timeout=None: _FakeResponse({"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0}),
    )
    assert finnhub.fetch_finnhub_quote("UNKNOWN", label="x", source_name="Finnhub", unit="€") is None


def test_fetch_finnhub_quote_returns_none_on_network_failure(monkeypatch):
    import requests

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(finnhub.requests, "get", _raise)
    assert finnhub.fetch_finnhub_quote("TTE.PA", label="x", source_name="Finnhub", unit="€") is None


def test_collect_donnees_finnhub_without_symbol_raises():
    with pytest.raises(ValueError):
        finnhub.collect_donnees_finnhub(db=None, engine=None, scope=None)


def test_collect_donnees_finnhub_returns_one_group_per_symbol(monkeypatch):
    monkeypatch.setattr(
        finnhub,
        "fetch_finnhub_quote",
        lambda symbol, label, source_name, unit: finnhub.CollectedItem(
            label=label, value=63.42, unit=unit, source_name=source_name, source_url="x", observed_at="0", symbol=symbol
        ),
    )
    groups = finnhub.collect_donnees_finnhub(db=None, engine=None, scope={"symbol": "TTE.PA"})
    assert len(groups) == 1
    label, items = groups[0]
    assert items[0].symbol == "TTE.PA"
