"""Tests de `agents/george_veille.py` -- réseau/LLM et écriture en base
mockés, même principe que `tests/test_jane_veille.py::collect_veille_web`
(source unique de vérité pour la synthèse multi-sources, pas de dédup à
tester ici puisqu'elle vit dans `agents/company_knowledge.py`)."""

import datetime

import agents.george_veille as george_veille
import agents.mistral_client as mistral_client
import agents.web_search as web_search
from ingestion.models import CompanyNewsKnowledge


def test_pick_daily_companies_is_deterministic_and_returns_n_companies(monkeypatch):
    fake_companies = [{"company_name": f"Société {i}", "symbol": None} for i in range(7)]
    monkeypatch.setattr(george_veille, "_all_companies", lambda db: fake_companies)

    fixed_now = datetime.datetime(2026, 9, 7, tzinfo=datetime.timezone.utc)

    class _FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    original = george_veille.datetime
    george_veille.datetime = _FakeDateTime
    try:
        first = george_veille._pick_daily_companies(db=None, n=3)
        second = george_veille._pick_daily_companies(db=None, n=3)
    finally:
        george_veille.datetime = original

    assert len(first) == 3
    # Déterministe : même jour, même tranche -- pas de hasard.
    assert first == second
    assert all(c in fake_companies for c in first)


def test_pick_daily_companies_wraps_around_circularly(monkeypatch):
    """Une tranche qui chevaucherait la fin de la liste doit reprendre au
    début plutôt que de renvoyer moins de `n` entreprises."""
    fake_companies = [{"company_name": f"Société {i}", "symbol": None} for i in range(5)]
    monkeypatch.setattr(george_veille, "_all_companies", lambda db: fake_companies)

    result = george_veille._pick_daily_companies(db=None, n=5)
    assert len(result) == 5


def test_pick_daily_companies_returns_empty_when_no_companies(monkeypatch):
    monkeypatch.setattr(george_veille, "_all_companies", lambda db: [])
    assert george_veille._pick_daily_companies(db=None) == []


def test_collect_company_news_requires_company_name():
    import pytest

    with pytest.raises(ValueError):
        george_veille.collect_company_news(db=None, engine=None, scope=None)
    with pytest.raises(ValueError):
        george_veille.collect_company_news(db=None, engine=None, scope={})


def test_collect_company_news_returns_empty_when_no_search_results(monkeypatch):
    monkeypatch.setattr(web_search, "search", lambda query, max_results=3: [])

    def _fail_if_called(*a, **k):
        raise AssertionError("mistral_client.complete ne doit pas être appelé sans résultat web")

    monkeypatch.setattr(mistral_client, "complete", _fail_if_called)

    groups = george_veille.collect_company_news(db=None, engine=None, scope={"company_name": "TotalEnergies", "symbol": "TTE.PA"})
    assert groups == []


def test_collect_company_news_synthesizes_multiple_sources_and_uses_small_model(monkeypatch):
    fake_results = [
        {"titre": "Reuters — TotalEnergies", "extrait": "TotalEnergies publie ses résultats trimestriels...", "url": "https://reuters.com/tte"},
        {"titre": "Les Échos — TotalEnergies", "extrait": "Le bénéfice net recule de...", "url": "https://lesechos.fr/tte"},
    ]
    monkeypatch.setattr(web_search, "search", lambda query, max_results=3: fake_results)

    captured = {}

    def fake_complete(system_prompt, user_message, model=None, **kwargs):
        captured["model"] = model
        captured["user_message"] = user_message
        return "TotalEnergies a publié des résultats en baisse, confirmés par deux sources."

    monkeypatch.setattr(mistral_client, "complete", fake_complete)

    entry = CompanyNewsKnowledge(
        company_name="TotalEnergies",
        symbol="TTE.PA",
        content="TotalEnergies a publié des résultats en baisse, confirmés par deux sources.",
        source_name="Recherche web (2 sources) — TotalEnergies",
        source_url="https://reuters.com/tte",
    )
    entry.id = 1
    entry.created_at = datetime.datetime(2026, 9, 7, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(
        george_veille.company_knowledge,
        "add_company_knowledge",
        lambda db, content, company_name, symbol=None, source_name="", source_url=None: entry,
    )

    groups = george_veille.collect_company_news(db=None, engine=None, scope={"company_name": "TotalEnergies", "symbol": "TTE.PA"})

    # mistral-small-latest, pas large -- même modèle qu'explain_decision/chat, pas le "gros" modèle de Jane.
    assert captured["model"] == mistral_client.MODEL_SMALL
    assert "Reuters" in captured["user_message"]
    assert "Les Échos" in captured["user_message"]

    label, items = groups[0]
    assert "ajoutée à company_news_knowledge" in label
    assert items[0].symbol == "TTE.PA"
    assert items[0].source_url == "https://reuters.com/tte"


def test_collect_company_news_reports_deduped_when_add_company_knowledge_skips(monkeypatch):
    monkeypatch.setattr(
        web_search,
        "search",
        lambda query, max_results=3: [{"titre": "Source", "extrait": "Déjà couvert.", "url": "https://example.com"}],
    )
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Résumé quasi identique à un existant.")
    monkeypatch.setattr(
        george_veille.company_knowledge,
        "add_company_knowledge",
        lambda db, content, company_name, symbol=None, source_name="", source_url=None: None,
    )

    groups = george_veille.collect_company_news(db=None, engine=None, scope={"company_name": "Neste", "symbol": None})
    label, items = groups[0]
    assert "quasi-doublon ignoré" in label
    assert items[0].symbol is None


def test_collect_company_news_for_untracked_biofuel_company_has_no_symbol(monkeypatch):
    """Une entreprise du secteur biocarburants/gaz renouvelables n'a pas de
    ligne `securities` -- `symbol` doit rester `None` de bout en bout (voir
    le piège FK déjà documenté pour AgentEvent.symbol/carry trade)."""
    monkeypatch.setattr(
        web_search,
        "search",
        lambda query, max_results=3: [{"titre": "Source", "extrait": "Actualité Neste.", "url": "https://example.com/neste"}],
    )
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Résumé Neste.")

    entry = CompanyNewsKnowledge(
        company_name="Neste", symbol=None, content="Résumé Neste.", source_name="x", source_url="https://example.com/neste"
    )
    entry.id = 1
    entry.created_at = datetime.datetime(2026, 9, 7, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(
        george_veille.company_knowledge,
        "add_company_knowledge",
        lambda db, content, company_name, symbol=None, source_name="", source_url=None: entry,
    )

    groups = george_veille.collect_company_news(db=None, engine=None, scope={"company_name": "Neste"})
    label, items = groups[0]
    assert items[0].symbol is None
