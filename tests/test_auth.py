"""Tests de `api/auth.py:require_user` — purs (pas de DB, pas de Docker,
pas de réseau), même tier que `tests/test_agents.py`. `require_user` est une
fonction `async` ordinaire (pas une route FastAPI) : elle est appelée
directement via `asyncio.run(...)` plutôt qu'au travers d'un `TestClient`,
pour ne pas dépendre de `pytest-asyncio` pour seulement 3 tests.
"""

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import api.auth as auth


def test_require_user_missing_credentials_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth.require_user(credentials=None))
    assert exc_info.value.status_code == 401


def test_require_user_invalid_token_returns_401(monkeypatch):
    async def fake_verify(token):
        return None

    monkeypatch.setattr(auth, "verify_supabase_token", fake_verify)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jeton-invalide")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth.require_user(credentials=creds))
    assert exc_info.value.status_code == 401


def test_require_user_valid_token_returns_user_id(monkeypatch):
    async def fake_verify(token):
        assert token == "jeton-valide"
        return {"id": "user-123", "email": "test@example.com"}

    monkeypatch.setattr(auth, "verify_supabase_token", fake_verify)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jeton-valide")

    user_id = asyncio.run(auth.require_user(credentials=creds))
    assert user_id == "user-123"


def test_verify_supabase_token_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    with pytest.raises(auth.SupabaseUnavailableError):
        asyncio.run(auth.verify_supabase_token("un-jeton"))


# --- Délai et nouvelle tentative vers Supabase Auth (octobre 2026) ---------
# `httpx.AsyncClient` est remplacé par un client branché sur un
# `httpx.MockTransport` : aucun appel réseau réel.


# --- require_cron_secret (octobre 2026) -----------------------------------
# Fonction sync ordinaire (pas de route FastAPI, pas de dépendance async) --
# appelée directement, même esprit que require_user ci-dessus.


def test_require_cron_secret_missing_env_var_returns_500(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        auth.require_cron_secret(x_cron_secret="peu-importe")
    assert exc_info.value.status_code == 500


def test_require_cron_secret_missing_header_returns_401(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "le-bon-secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_cron_secret(x_cron_secret=None)
    assert exc_info.value.status_code == 401


def test_require_cron_secret_wrong_value_returns_401(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "le-bon-secret")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_cron_secret(x_cron_secret="un-mauvais-secret")
    assert exc_info.value.status_code == 401


def test_require_cron_secret_correct_value_returns_none(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "le-bon-secret")
    assert auth.require_cron_secret(x_cron_secret="le-bon-secret") is None


def _mock_client(monkeypatch, handler):
    real_client = auth.httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=auth.httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(auth.httpx, "AsyncClient", factory)


def _set_env(monkeypatch, url="https://projet.supabase.co"):
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "cle-anon")


def test_verify_supabase_token_retries_once_after_a_timeout(monkeypatch):
    _set_env(monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise auth.httpx.ConnectTimeout("délai dépassé", request=request)
        return auth.httpx.Response(200, json={"id": "user-123"})

    _mock_client(monkeypatch, handler)
    assert asyncio.run(auth.verify_supabase_token("jeton")) == {"id": "user-123"}
    assert len(calls) == 2


def test_verify_supabase_token_names_the_error_type_after_last_attempt(monkeypatch):
    _set_env(monkeypatch)

    def handler(request):
        raise auth.httpx.ReadTimeout("", request=request)

    _mock_client(monkeypatch, handler)
    with pytest.raises(auth.SupabaseUnavailableError) as exc_info:
        asyncio.run(auth.verify_supabase_token("jeton"))
    # Le message n'est plus vide : il nomme le type d'erreur réel.
    assert "ReadTimeout" in str(exc_info.value)


def test_verify_supabase_token_does_not_retry_an_http_answer(monkeypatch):
    _set_env(monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        return auth.httpx.Response(401, json={"msg": "invalid JWT"})

    _mock_client(monkeypatch, handler)
    assert asyncio.run(auth.verify_supabase_token("jeton-expire")) is None
    assert len(calls) == 1


def test_verify_supabase_token_strips_pasted_whitespace_from_config(monkeypatch):
    _set_env(monkeypatch, url="  https://projet.supabase.co/\n")
    seen = []

    def handler(request):
        seen.append(str(request.url))
        assert request.headers["apikey"] == "cle-anon"
        return auth.httpx.Response(200, json={"id": "user-123"})

    _mock_client(monkeypatch, handler)
    asyncio.run(auth.verify_supabase_token("jeton"))
    assert seen == ["https://projet.supabase.co/auth/v1/user"]
