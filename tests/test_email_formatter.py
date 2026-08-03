"""Tests de `agents/email_formatter.py` — pur, sans réseau (Mistral moqué,
même précédent que le reste de `tests/test_agents.py`)."""
import agents.mistral_client as mistral_client
from agents.email_formatter import format_email_body
from agents.mistral_client import MistralUnavailableError


def test_format_email_body_returns_empty_text_unchanged():
    assert format_email_body("") == ""
    assert format_email_body("   ") == "   "


def test_format_email_body_returns_mistral_output(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Bonjour,\n\nTexte reformulé.\n\nGeorge")
    result = format_email_body("Figure détectée : Double Bottom, confiance 60%.")
    assert result == "Bonjour,\n\nTexte reformulé.\n\nGeorge"


def test_format_email_body_falls_back_to_raw_text_when_mistral_unavailable(monkeypatch):
    def _raise(*a, **k):
        raise MistralUnavailableError("clé manquante")

    monkeypatch.setattr(mistral_client, "complete", _raise)
    raw = "Figure détectée : Double Bottom, confiance 60%."
    assert format_email_body(raw) == raw
