"""CORS de l'API (pur : aucune base, aucun réseau). Le navigateur doit
pouvoir envoyer un PATCH vers /bonds/alerts/thresholds/{id} (édition des
seuils depuis l'onglet web "Obligataire") — sans "PATCH" dans
`allow_methods`, la requête préalable OPTIONS est refusée et l'édition échoue
côté navigateur alors qu'elle passe en curl."""

from fastapi.testclient import TestClient

from api.main import app


def test_preflight_allows_patch_from_the_web_app():
    client = TestClient(app)
    response = client.options(
        "/bonds/alerts/thresholds/1",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_cors_origins_adds_extra_origins_from_env(monkeypatch):
    from api.main import cors_origins

    monkeypatch.setenv("CORS_EXTRA_ORIGINS", " https://george-web.onrender.com/ ,, https://george.example.org")
    origins = cors_origins()
    assert "http://localhost:5173" in origins
    assert "https://george-web.onrender.com" in origins
    assert "https://george.example.org" in origins
    assert "" not in origins


def test_cors_origins_defaults_to_dev_server(monkeypatch):
    from api.main import cors_origins

    monkeypatch.delenv("CORS_EXTRA_ORIGINS", raising=False)
    assert cors_origins() == ["http://localhost:5173", "http://127.0.0.1:5173"]
