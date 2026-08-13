"""Tests de `agents/jane.py:reformulate_formal` -- pur, sans réseau (Mistral
moqué), même précédent que `tests/test_email_formatter.py` pour la fonction
analogue côté partage par email."""
import agents.mistral_client as mistral_client
from agents.jane import reformulate_formal
from agents.mistral_client import MistralUnavailableError


def test_reformulate_formal_returns_empty_text_unchanged():
    assert reformulate_formal("") == ""
    assert reformulate_formal("   ") == "   "


def test_reformulate_formal_returns_mistral_output(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Texte reformulé, registre soutenu.")
    result = reformulate_formal("Detection: Bull Flag, confiance 60%.")
    assert result == "Texte reformulé, registre soutenu."


def test_reformulate_formal_falls_back_to_raw_text_when_mistral_unavailable(monkeypatch):
    def _raise(*a, **k):
        raise MistralUnavailableError("clé API manquante")

    monkeypatch.setattr(mistral_client, "complete", _raise)
    raw = "Detection: Bull Flag, confiance 60%."
    assert reformulate_formal(raw) == raw
