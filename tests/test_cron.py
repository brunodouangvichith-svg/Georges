"""Tests de `api/routers/cron.py` -- purs (pas de DB, pas de Docker, pas de
réseau), même esprit que `tests/test_auth.py`. Les fonctions `_run_*`
(appelées en tâche de fond) sont monkeypatchées : aucune ne touche
réellement la DB/un service externe dans ces tests, seul le routage/
l'authentification par secret partagé est couvert ici. `TestClient`
exécute les `BackgroundTasks` de façon synchrone avant de renvoyer la
réponse HTTP, donc une fonction monkeypatchée est déjà appelée au moment
où `client.post(...)` revient."""

from fastapi.testclient import TestClient

import api.routers.cron as cron
from api.main import app

CRON_SECRET = "le-secret-de-test"


def _client():
    return TestClient(app)


def test_post_cron_route_without_secret_header_returns_401(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    with _client() as client:
        response = client.post("/cron/energy-prices")
    assert response.status_code == 401


def test_post_cron_route_with_wrong_secret_returns_401(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    with _client() as client:
        response = client.post("/cron/energy-prices", headers={"X-Cron-Secret": "mauvais-secret"})
    assert response.status_code == 401


def test_post_cron_route_with_missing_server_secret_returns_500(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    with _client() as client:
        response = client.post("/cron/energy-prices", headers={"X-Cron-Secret": "peu-importe"})
    assert response.status_code == 500


def test_post_cron_energy_prices_with_correct_secret_runs_job_and_returns_started(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    called = []
    monkeypatch.setattr(cron, "_run_energy_prices", lambda: called.append(True))

    with _client() as client:
        response = client.post("/cron/energy-prices", headers={"X-Cron-Secret": CRON_SECRET})

    assert response.status_code == 200
    assert response.json() == {"status": "started", "job": "energy-prices"}
    assert called == [True]


def test_all_cron_routes_require_the_secret_and_schedule_their_job(monkeypatch):
    """Un seul test paramétrique plutôt qu'un test par route : ce qui varie
    d'une route à l'autre (le nom de la fonction `_run_*`, le `job` renvoyé)
    est couvert exhaustivement sans dupliquer la même assertion huit fois."""
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    routes_and_jobs = [
        ("/cron/bonds", "_run_bonds", "bonds"),
        ("/cron/energy-prices", "_run_energy_prices", "energy-prices"),
        ("/cron/fundamentals", "_run_fundamentals", "fundamentals"),
        ("/cron/george-veille", "_run_george_veille", "george-veille"),
        ("/cron/geopolitical-veille", "_run_geopolitical_veille", "geopolitical-veille"),
        ("/cron/jane-veille-web", "_run_jane_veille_web", "jane-veille-web"),
        ("/cron/price-history-and-detection", "_run_price_history_and_detection", "price-history-and-detection"),
        ("/cron/confidence-model-training", "_run_confidence_model_training", "confidence-model-training"),
    ]
    with _client() as client:
        for path, fn_name, expected_job in routes_and_jobs:
            called = []
            monkeypatch.setattr(cron, fn_name, lambda called=called: called.append(True))

            response = client.post(path, headers={"X-Cron-Secret": CRON_SECRET})
            assert response.status_code == 200, path
            assert response.json() == {"status": "started", "job": expected_job}, path
            assert called == [True], path

            no_auth_response = client.post(path)
            assert no_auth_response.status_code == 401, path
