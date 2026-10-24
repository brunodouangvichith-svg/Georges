"""CORS de l'API (pur : aucune base, aucun réseau). Le navigateur doit
pouvoir envoyer un PATCH vers /bonds/alerts/thresholds/{id} (édition des
seuils depuis l'onglet web "Obligataire") — sans "PATCH" dans
`allow_methods`, la requête préalable OPTIONS est refusée et l'édition échoue
côté navigateur alors qu'elle passe en curl. Les origines viennent uniquement
de `CORS_EXTRA_ORIGINS` (plus de localhost par défaut)."""

import importlib

import pytest

from fastapi.testclient import TestClient

import api.main

SITE = "https://george-web-43l7.onrender.com"


@pytest.fixture(autouse=True)
def _restore_api_main(monkeypatch):
    yield
    # Après chaque test (variable d'environnement déjà restaurée par
    # monkeypatch), recharger api.main pour ne pas laisser aux autres tests
    # une appli construite avec les origines de ce test.
    monkeypatch.undo()
    importlib.reload(api.main)


def _app_with_origins(monkeypatch, value):
    # Le middleware CORS est construit à l'import : on recharge le module
    # avec la variable d'environnement voulue.
    monkeypatch.setenv("CORS_EXTRA_ORIGINS", value)
    return importlib.reload(api.main).app


def _preflight(app, origin):
    return TestClient(app).options(
        "/bonds/alerts/thresholds/1",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_preflight_allows_patch_from_the_web_site(monkeypatch):
    response = _preflight(_app_with_origins(monkeypatch, SITE), SITE)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == SITE
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_preflight_rejects_localhost_by_default(monkeypatch):
    response = _preflight(_app_with_origins(monkeypatch, SITE), "http://localhost:5173")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_parses_env(monkeypatch):
    monkeypatch.setenv("CORS_EXTRA_ORIGINS", f" {SITE}/ ,, https://george.example.org, {SITE}")
    assert api.main.cors_origins() == [SITE, "https://george.example.org"]


def test_cors_origins_empty_without_env(monkeypatch):
    monkeypatch.delenv("CORS_EXTRA_ORIGINS", raising=False)
    assert api.main.cors_origins() == []
