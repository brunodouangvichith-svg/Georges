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
