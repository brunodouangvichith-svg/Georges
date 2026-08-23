"""Tests de `agents/jane.py:second_opinion` et `_knowledge_query` -- réseau
et DB mockés, même principe que `tests/test_jane_reformulation.py` pour
`reformulate_formal`."""

import datetime

import agents.jane as jane
import agents.mistral_client as mistral_client
from ingestion.models import Decision, JaneKnowledge, PatternDetected, Security


class _FakeDB:
    def __init__(self, security):
        self._security = security

    def get(self, model, symbol):
        return self._security if symbol == self._security.symbol else None


def _decision(symbol="AIR.PA"):
    return Decision(
        symbol=symbol, decision_type="Achat", entry_price=129.5, take_profit=140.0, stop_loss=120.0, confidence=77.0
    )


def _security(symbol="AIR.PA"):
    return Security(symbol=symbol, name="Airbus", country="FR", currency="EUR", sector="Aéronautique", theme=None)


def _pattern(symbol="AIR.PA", pattern_type="Bull Flag"):
    return PatternDetected(
        symbol=symbol,
        pattern_type=pattern_type,
        detected_at=datetime.datetime(2026, 7, 20, tzinfo=datetime.timezone.utc),
        confidence=77.0,
        context={},
    )


def test_knowledge_query_combines_decision_type_and_pattern_type():
    assert jane._knowledge_query(_decision(), _pattern()) == "Achat Bull Flag"


def test_knowledge_query_without_pattern_is_decision_type_only():
    assert jane._knowledge_query(_decision(), None) == "Achat"


def test_second_opinion_injects_relevant_knowledge_into_context(monkeypatch):
    captured = {}

    def fake_complete(system_prompt, user_message, model=None, temperature=0.3, max_retries=3):
        captured["user_message"] = user_message
        return "Note de Jane."

    entry = JaneKnowledge(
        content="Sharpe = (Rp - Rf) / sigma(Rp).",
        source_name="Jane_Synthese_Connaissances.md — 2.5 Mesures de performance",
        source_url=None,
    )

    monkeypatch.setattr(jane, "find_pattern_for_decision", lambda db, decision: None)
    monkeypatch.setattr(jane.jane_knowledge, "search_jane_knowledge", lambda db, query, limit=5: [entry])
    monkeypatch.setattr(mistral_client, "complete", fake_complete)

    result = jane.second_opinion(_FakeDB(_security()), _decision())

    assert result == "Note de Jane."
    assert "Sharpe" in captured["user_message"]
    assert "Jane_Synthese_Connaissances.md" in captured["user_message"]


def test_second_opinion_works_with_no_relevant_knowledge_yet(monkeypatch):
    """Base `jane_knowledge` pas encore amorcée -- ne doit jamais planter,
    ni faire inventer une connaissance au LLM (voir la consigne ajoutée dans
    `jane_second_opinion_system.txt`)."""
    monkeypatch.setattr(jane, "find_pattern_for_decision", lambda db, decision: None)
    monkeypatch.setattr(jane.jane_knowledge, "search_jane_knowledge", lambda db, query, limit=5: [])
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Note de Jane.")

    result = jane.second_opinion(_FakeDB(_security()), _decision())
    assert result == "Note de Jane."
