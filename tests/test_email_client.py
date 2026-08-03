"""Tests de `notifications/email_client.py` — pur, sans réseau réel (httpx
moqué via monkeypatch, même précédent que les tests d'`agents/mistral_client.py`
côté `tests/test_api.py`)."""
import base64

import httpx
import pytest

import notifications.email_client as email_client


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_send_email_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(email_client.EmailUnavailableError):
        email_client.send_email("a@b.com", "Sujet", "Texte")


def test_send_email_builds_correct_payload_without_attachment(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(200)

    monkeypatch.setattr(httpx, "post", fake_post)
    email_client.send_email("investisseur@example.com", "George explique", "Contenu réel.")

    assert captured["url"] == email_client.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer re_test"
    assert captured["json"]["to"] == ["investisseur@example.com"]
    assert captured["json"]["subject"] == "George explique"
    assert captured["json"]["text"] == "Contenu réel."
    assert "attachments" not in captured["json"]


def test_send_email_includes_base64_attachment_when_provided(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _FakeResponse(200)

    monkeypatch.setattr(httpx, "post", fake_post)
    email_client.send_email(
        "investisseur@example.com", "Sujet", "Texte", attachment_bytes=b"PNGDATA", attachment_filename="ACA.PA.png"
    )

    attachment = captured["json"]["attachments"][0]
    assert attachment["filename"] == "ACA.PA.png"
    assert base64.b64decode(attachment["content"]) == b"PNGDATA"


def test_send_email_raises_on_non_2xx_response(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(403, "Domaine non vérifié"))
    with pytest.raises(email_client.EmailUnavailableError, match="403"):
        email_client.send_email("a@b.com", "Sujet", "Texte")


def test_send_email_raises_on_network_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")

    def fake_post(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(email_client.EmailUnavailableError):
        email_client.send_email("a@b.com", "Sujet", "Texte")
