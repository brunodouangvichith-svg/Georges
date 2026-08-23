"""Tests de `agents/jane_veille.py:collect_veille_methodologique` -- réseau/
LLM et écriture en base mockés, même principe que `tests/test_collectors.py`
pour `synthesis.py` (source unique, pas de recoupement multi-source à
tester ici)."""

import datetime

import pytest

import agents.jane_veille as jane_veille
import agents.mistral_client as mistral_client
from ingestion.models import JaneKnowledge


def test_collect_veille_methodologique_requires_source_name_and_content():
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(db=None, engine=None, scope=None)
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(db=None, engine=None, scope={"source_name": "Investopedia"})


def test_collect_veille_methodologique_adds_summary_to_jane_knowledge(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Le ratio de Sharpe mesure le rendement ajusté au risque.")

    entry = JaneKnowledge(
        content="Le ratio de Sharpe mesure le rendement ajusté au risque.",
        source_name="Investopedia",
        source_url="https://www.investopedia.com/sharpe-ratio",
    )
    entry.id = 1
    entry.created_at = datetime.datetime(2026, 8, 23, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: entry)

    groups = jane_veille.collect_veille_methodologique(
        db=None,
        engine=None,
        scope={
            "source_name": "Investopedia",
            "content": "Texte brut de la page Investopedia sur le ratio de Sharpe...",
            "source_url": "https://www.investopedia.com/sharpe-ratio",
        },
    )
    assert len(groups) == 1
    label, items = groups[0]
    assert "Investopedia" in label
    assert "ajoutée à jane_knowledge" in label
    assert len(items) == 1
    assert items[0].value == "Le ratio de Sharpe mesure le rendement ajusté au risque."
    assert items[0].source_name == "Investopedia"
    assert items[0].observed_at == "2026-08-23T00:00:00+00:00"


def test_collect_veille_methodologique_reports_deduped_when_add_knowledge_skips(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Résumé quasi identique à un existant.")
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: None)

    groups = jane_veille.collect_veille_methodologique(
        db=None, engine=None, scope={"source_name": "BabyPips", "content": "Texte déjà couvert par une entrée existante."}
    )
    label, items = groups[0]
    assert "quasi-doublon ignoré" in label
    # La valeur reste le résumé réel malgré le doublon -- observable dans le flux d'activité même non retenu en base.
    assert items[0].value == "Résumé quasi identique à un existant."
