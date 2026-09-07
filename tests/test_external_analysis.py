"""Tests de `agents/external_analysis.py` — pur, sans réseau : `yfinance`
et `mistral_client.complete`/`detect_all` sont tous mockés."""

import pandas as pd

import agents.external_analysis as external_analysis
import agents.mistral_client as mistral_client
from engine.patterns import PatternMatch


def test_extract_company_name_returns_none_for_no_company_marker(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "AUCUNE")
    assert external_analysis.extract_company_name("Quelle est la météo à Paris ?") is None


def test_extract_company_name_passes_allow_fallback_false(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, question, model=None, allow_fallback=True):
        captured["allow_fallback"] = allow_fallback
        return "Haffner Energy"

    monkeypatch.setattr(mistral_client, "complete", fake_complete)
    result = external_analysis.extract_company_name("que penses tu de Haffner ?")
    assert result == "Haffner Energy"
    assert captured["allow_fallback"] is False


def test_extract_company_name_returns_none_when_mistral_unavailable(monkeypatch):
    def fail(*a, **k):
        raise mistral_client.MistralUnavailableError("indisponible")

    monkeypatch.setattr(mistral_client, "complete", fail)
    assert external_analysis.extract_company_name("que penses tu de Haffner ?") is None


class _FakeSearch:
    def __init__(self, quotes):
        self.quotes = quotes


def test_resolve_ticker_filters_out_warrants(monkeypatch):
    monkeypatch.setattr(
        external_analysis.yf,
        "Search",
        lambda query, max_results=8: _FakeSearch(
            [
                {"quoteType": "EQUITY", "shortname": "HAFFNER ENERGY BSA", "longname": "Haffner Energy SA", "symbol": "HAFBS.PA", "exchange": "PAR"},
                {"quoteType": "EQUITY", "shortname": "HAFFNER ENERGY", "longname": "Haffner Energy S.A.", "symbol": "ALHAF.PA", "exchange": "PAR"},
            ]
        ),
    )
    assert external_analysis.resolve_ticker("Haffner Energy") == "ALHAF.PA"


def test_resolve_ticker_prefers_paris_listing(monkeypatch):
    monkeypatch.setattr(
        external_analysis.yf,
        "Search",
        lambda query, max_results=8: _FakeSearch(
            [
                {"quoteType": "EQUITY", "shortname": "HAFFNER ENERGY", "longname": "Haffner Energy", "symbol": "X1B.F", "exchange": "FRA"},
                {"quoteType": "EQUITY", "shortname": "HAFFNER ENERGY", "longname": "Haffner Energy", "symbol": "ALHAF.PA", "exchange": "PAR"},
            ]
        ),
    )
    assert external_analysis.resolve_ticker("Haffner Energy") == "ALHAF.PA"


def test_resolve_ticker_handles_explicit_none_shortname_or_longname(monkeypatch):
    """Régression : `.get(key, "")` ne couvre que la clé absente, pas une
    valeur explicitement `None` — `.upper()` sur `None` levait
    `AttributeError`, hors du `try/except` qui n'entoure que `yf.Search`."""
    monkeypatch.setattr(
        external_analysis.yf,
        "Search",
        lambda query, max_results=8: _FakeSearch(
            [{"quoteType": "EQUITY", "shortname": None, "longname": None, "symbol": "ALHAF.PA", "exchange": "PAR"}]
        ),
    )
    assert external_analysis.resolve_ticker("Haffner Energy") == "ALHAF.PA"


def test_resolve_ticker_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(external_analysis.yf, "Search", lambda query, max_results=8: _FakeSearch([]))
    assert external_analysis.resolve_ticker("Une entreprise inexistante") is None


def test_resolve_ticker_returns_none_on_exception(monkeypatch):
    def fail(query, max_results=8):
        raise RuntimeError("yfinance indisponible")

    monkeypatch.setattr(external_analysis.yf, "Search", fail)
    assert external_analysis.resolve_ticker("Haffner Energy") is None


class _FakeTicker:
    def __init__(self, df):
        self._df = df

    def history(self, period):
        return self._df


def test_analyze_ticker_returns_none_when_history_is_empty(monkeypatch):
    monkeypatch.setattr(external_analysis.yf, "Ticker", lambda ticker: _FakeTicker(pd.DataFrame()))
    assert external_analysis.analyze_ticker("ALHAF.PA") is None


def test_analyze_ticker_returns_none_when_a_column_is_missing(monkeypatch):
    """Régression : un historique sans l'une des 5 colonnes attendues (ex.
    un type de titre inhabituel) levait `KeyError`, non couvert par le
    `except ValueError` d'origine autour de `detect_all` seul."""
    df = pd.DataFrame({"Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0]}, index=[pd.Timestamp("2026-01-01")])
    monkeypatch.setattr(external_analysis.yf, "Ticker", lambda ticker: _FakeTicker(df))
    assert external_analysis.analyze_ticker("ALHAF.PA") is None


def test_analyze_ticker_returns_the_most_confident_match(monkeypatch):
    df = pd.DataFrame(
        {"Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0], "Volume": [1000]},
        index=[pd.Timestamp("2026-01-01")],
    )
    monkeypatch.setattr(external_analysis.yf, "Ticker", lambda ticker: _FakeTicker(df))

    low_confidence = PatternMatch(pattern_type="Bull Flag", detected_at=pd.Timestamp("2026-01-01"), confidence=40.0, context={})
    high_confidence = PatternMatch(pattern_type="Double Bottom", detected_at=pd.Timestamp("2026-01-01"), confidence=80.0, context={})
    monkeypatch.setattr(external_analysis, "detect_all", lambda df: [low_confidence, high_confidence])

    result = external_analysis.analyze_ticker("ALHAF.PA")
    assert result.pattern_type == "Double Bottom"
    assert result.confidence == 80.0


def test_analyze_ticker_returns_none_when_no_pattern_detected(monkeypatch):
    df = pd.DataFrame(
        {"Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0], "Volume": [1000]},
        index=[pd.Timestamp("2026-01-01")],
    )
    monkeypatch.setattr(external_analysis.yf, "Ticker", lambda ticker: _FakeTicker(df))
    monkeypatch.setattr(external_analysis, "detect_all", lambda df: [])
    assert external_analysis.analyze_ticker("ALHAF.PA") is None
