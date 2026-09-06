"""Tests de `agents/jane.py:ask` -- réseau et DB mockés, même principe que
`tests/test_jane_second_opinion.py` pour `second_opinion`."""

import agents.jane as jane
import agents.mistral_client as mistral_client
from ingestion.models import JaneKnowledge


class _FakeDB:
    pass


def test_ask_injects_matched_knowledge_into_context(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, user_message, model=None, temperature=0.3, max_retries=3):
        captured["user_message"] = user_message
        return "Le ratio de Sharpe se calcule ainsi..."

    entry = JaneKnowledge(
        content="Sharpe = (Rp - Rf) / sigma(Rp).",
        source_name="Jane_Synthese_Connaissances.md — 2.5 Mesures de performance",
        source_url=None,
    )

    captured_query = {}

    def fake_search(db, query, limit=5):
        captured_query["query"] = query
        return [entry]

    monkeypatch.setattr(jane.jane_knowledge, "search_jane_knowledge", fake_search)
    monkeypatch.setattr(mistral_client, "complete", fake_complete)

    result = jane.ask(_FakeDB(), "Comment calcule-t-on le ratio de Sharpe ?")

    assert result == "Le ratio de Sharpe se calcule ainsi..."
    assert captured_query["query"] == "Comment calcule-t-on le ratio de Sharpe ?"
    assert "Sharpe" in captured["user_message"]
    assert "Jane_Synthese_Connaissances.md" in captured["user_message"]


def test_ask_with_no_matching_knowledge_still_calls_llm_with_empty_list(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, user_message, model=None, temperature=0.3, max_retries=3):
        captured["user_message"] = user_message
        return "Je n'ai pas d'information indexée sur ce sujet."

    monkeypatch.setattr(jane.jane_knowledge, "search_jane_knowledge", lambda db, query, limit=5: [])
    monkeypatch.setattr(mistral_client, "complete", fake_complete)

    result = jane.ask(_FakeDB(), "Question hors sujet")

    assert result == "Je n'ai pas d'information indexée sur ce sujet."
    assert '"connaissances_pertinentes": []' in captured["user_message"]
