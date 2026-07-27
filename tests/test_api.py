"""Tests d'intégration de l'API FastAPI (Phase 3).

Nécessite un démon Docker local (testcontainers lance une instance
TimescaleDB jetable, migrée puis peuplée d'un jeu de données minimal) — voir
`database_url` dans `conftest.py`. Le moteur SQLAlchemy partagé de
`api.deps` (créé une fois à l'import, avant que l'URL de test soit connue)
est remplacé pour la durée du test par un moteur pointant vers le conteneur.
"""

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import agents.mistral_client as mistral_client
import api.deps as deps
from api.main import app
from ingestion.models import AgentEvent, Basket, BasketSecurity, Decision, PatternDetected, PriceOHLCV, Security


def _fake_complete(system_prompt, user_message, model=None, temperature=0.3, max_retries=3):
    """Remplace `agents.mistral_client.complete` dans les tests : renvoie le
    contexte JSON reçu tel quel plutôt qu'un vrai texte généré, pour vérifier
    (tâche 6 de la Phase 4) que les valeurs numériques réelles transmises en
    contexte se retrouvent bien dans la réponse — sans appel réseau ni clé
    API. Aucun de ces tests n'invente un chiffre : ils vérifient qu'aucun
    n'est perdu en chemin."""
    return f"[{model}] {user_message}"


def _fake_embed(texts, model=None):
    from ingestion.models import EMBEDDING_DIM

    return [[0.0] * EMBEDDING_DIM for _ in texts]


@pytest.fixture()
def mock_llm(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", _fake_complete)
    monkeypatch.setattr(mistral_client, "embed", _fake_embed)


@pytest.fixture()
def client(database_url, monkeypatch):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")

    test_engine = create_engine(database_url, future=True)
    monkeypatch.setattr(deps, "engine", test_engine)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=test_engine, autoflush=False, future=True))

    # 30 séances se terminant "aujourd'hui", pour que la figure détectée
    # tombe dans la fenêtre d'activité du George Index (voir
    # engine/george_index.md:ACTIVE_WINDOW_SESSIONS).
    base_ts = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=29)
    price_rows = [
        {
            "symbol": "AAA.PA",
            "ts": base_ts + pd.Timedelta(days=i),
            "open": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "close": 100 + i,
            "volume": 1_000_000,
        }
        for i in range(30)
    ]

    with test_engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [
                {"symbol": "AAA.PA", "name": "Alpha SA", "country": "FR", "currency": "EUR", "sector": "Tech", "theme": None},
                {"symbol": "BBB.PA", "name": "Beta SA", "country": "FR", "currency": "EUR", "sector": "Finance", "theme": None},
            ],
        )
        conn.execute(Basket.__table__.insert(), [{"id": 1, "name": "Tech FR", "type": "secteur"}])
        conn.execute(BasketSecurity.__table__.insert(), [{"basket_id": 1, "symbol": "AAA.PA", "weight": None}])
        conn.execute(PriceOHLCV.__table__.insert(), price_rows)
        conn.execute(
            PatternDetected.__table__.insert(),
            [
                # Même `detected_at` que la ligne suivante, confiance plus
                # basse : régression sur le tri de list_security_patterns
                # (voir test_list_security_patterns_prefers_higher_confidence_on_tie).
                {
                    "symbol": "AAA.PA",
                    "pattern_type": "Double Bottom",
                    "detected_at": price_rows[-1]["ts"],
                    "confidence": 20.0,
                    "context": {},
                },
                {
                    "symbol": "AAA.PA",
                    "pattern_type": "Bull Flag",
                    "detected_at": price_rows[-1]["ts"],
                    "confidence": 77.0,
                    "context": {},
                },
            ],
        )
        conn.execute(
            Decision.__table__.insert(),
            [
                {
                    "symbol": "AAA.PA",
                    "decision_type": "Achat",
                    "entry_price": 129.0,
                    "take_profit": 140.0,
                    "stop_loss": 120.0,
                    "confidence": 77.0,
                    "rationale": "test",
                }
            ],
        )
        conn.execute(
            AgentEvent.__table__.insert(),
            [
                {
                    "agent_name": "presse",
                    "description": "test event",
                    "status": "validated",
                    "symbol": "AAA.PA",
                    "context": {},
                }
            ],
        )

    with TestClient(app) as test_client:
        yield test_client

    command.downgrade(cfg, "base")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_securities(client):
    resp = client.get("/securities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {s["symbol"] for s in body["items"]} == {"AAA.PA", "BBB.PA"}


def test_list_securities_filtered_by_basket(client):
    resp = client.get("/securities", params={"basket_id": 1})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "AAA.PA"


def test_list_securities_pagination(client):
    resp = client.get("/securities", params={"limit": 1, "offset": 1})
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["limit"] == 1
    assert body["offset"] == 1


def test_security_not_found_returns_404(client):
    resp = client.get("/securities/NOPE.PA/patterns")
    assert resp.status_code == 404


def test_list_security_patterns(client):
    resp = client.get("/securities/AAA.PA/patterns")
    body = resp.json()
    assert body["total"] == 2
    assert body["items"][0]["pattern_type"] == "Bull Flag"


def test_list_security_patterns_prefers_higher_confidence_on_tie(client):
    """`AAA.PA` a deux figures avec le même `detected_at` (voir la fixture
    `client`) — sans tri secondaire par confiance, Postgres peut renvoyer
    n'importe laquelle en premier pour `limit=1` (constaté contre une vraie
    base : systématiquement la moins confiante). La plus confiante doit
    gagner de façon déterministe."""
    resp = client.get("/securities/AAA.PA/patterns", params={"limit": 1})
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["pattern_type"] == "Bull Flag"
    assert body["items"][0]["confidence"] == 77.0


def test_list_security_prices_chronological_order(client):
    resp = client.get("/securities/AAA.PA/prices", params={"limit": 5})
    body = resp.json()
    assert body["total"] == 30
    closes = [row["close"] for row in body["items"]]
    assert closes == sorted(closes)


def test_list_baskets(client):
    resp = client.get("/baskets")
    assert resp.status_code == 200
    assert [b["name"] for b in resp.json()] == ["Tech FR"]


def test_george_index_for_basket_with_active_pattern(client):
    resp = client.get("/baskets/1/george-index")
    assert resp.status_code == 200
    body = resp.json()
    assert body["basket_name"] == "Tech FR"
    assert body["george_index"] is not None


def test_george_index_basket_not_found_returns_404(client):
    resp = client.get("/baskets/999/george-index")
    assert resp.status_code == 404


def test_list_decisions_filtered_by_status(client):
    resp = client.get("/decisions", params={"status": "Achat"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["decision_type"] == "Achat"

    resp = client.get("/decisions", params={"status": "Alléger"})
    assert resp.json()["total"] == 0


def test_list_decisions_filtered_by_basket(client):
    resp = client.get("/decisions", params={"basket_id": 1})
    assert resp.json()["total"] == 1

    resp = client.get("/decisions", params={"basket_id": 999})
    assert resp.json()["total"] == 0


def test_list_agent_activity_filtered_by_status(client):
    resp = client.get("/agents/activity", params={"status": "validated"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["agent_name"] == "presse"

    resp = client.get("/agents/activity", params={"status": "quarantine"})
    assert resp.json()["total"] == 0


def test_db_unreachable_returns_503_with_cors_headers(monkeypatch):
    """Ne dépend pas de Docker/testcontainers : une base injoignable doit
    renvoyer un 503 propre (pas un crash) *avec* les en-têtes CORS —
    régression sur un piège Starlette où un handler enregistré pour la
    classe `Exception` nue est redirigé vers `ServerErrorMiddleware`,
    au-dessus de `CORSMiddleware`, qui ne repasse alors jamais par l'ajout
    des en-têtes CORS (d'où une erreur CORS trompeuse côté navigateur au
    lieu du vrai message). Voir `api/main.py:database_exception_handler`,
    qui cible spécifiquement `SQLAlchemyError` pour rester sous
    `CORSMiddleware`."""
    broken_engine = create_engine(
        "postgresql+psycopg://nobody:nobody@localhost:59999/nope",
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr(deps, "engine", broken_engine)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=broken_engine, autoflush=False, future=True))

    with TestClient(app) as broken_client:
        resp = broken_client.get("/baskets", headers={"Origin": "http://localhost:5173"})

    assert resp.status_code == 503
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_chat_answers_cite_real_data(client, mock_llm):
    resp = client.post("/chat", json={"question": "Que penses-tu de Alpha SA ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    # Le titre reconnu ("Alpha SA") doit apparaître dans le contexte transmis
    # au LLM, avec sa dernière décision/figure réelle — pas des chiffres
    # inventés (tâche 6 de la Phase 4).
    assert "AAA.PA" in answer
    assert "129.0" in answer
    assert "77.0" in answer


def test_chat_with_no_recognized_security_says_so_via_empty_context(client, mock_llm):
    resp = client.post("/chat", json={"question": "Quelle est la météo à Paris ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert '"titres_reconnus": []' in answer


def _get_decision_id(client) -> int:
    resp = client.get("/decisions")
    return resp.json()["items"][0]["id"]


def test_decision_explanation_cites_real_numbers(client, mock_llm):
    decision_id = _get_decision_id(client)
    resp = client.post(f"/decisions/{decision_id}/explanation", json={"include_second_opinion": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["second_opinion"] is None
    assert "129.0" in body["explanation"]
    assert "140.0" in body["explanation"]
    assert "77.0" in body["explanation"]
    # Sur l'égalité de `detected_at` entre Double Bottom et Bull Flag, c'est
    # la figure la plus confiante qui doit être rattachée à la décision (même
    # règle de départage qu'en Phase 3, voir list_security_patterns).
    assert "Bull Flag" in body["explanation"]


def test_decision_explanation_with_second_opinion_calls_jane_first(client, mock_llm):
    decision_id = _get_decision_id(client)
    resp = client.post(f"/decisions/{decision_id}/explanation", json={"include_second_opinion": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["second_opinion"] is not None
    assert "mistral-large-latest" in body["second_opinion"]  # appel LLM distinct, modèle de Jane
    # George arbitre : sa propre explication (mistral-small-latest) doit
    # recevoir la note de Jane dans son contexte, pas seulement Jane
    # elle-même produire une note isolée.
    assert "mistral-small-latest" in body["explanation"]
    assert "mistral-large-latest" in body["explanation"]


def test_decision_explanation_unknown_decision_returns_404(client, mock_llm):
    resp = client.post("/decisions/999999/explanation", json={"include_second_opinion": False})
    assert resp.status_code == 404


def test_create_report_for_basket_cites_real_data(client, mock_llm):
    resp = client.post("/reports", json={"basket_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "basket:1"
    assert "Tech FR" in body["content"]
    assert "77.0" in body["content"]  # confiance de la décision active du panier

    listed = client.get("/reports", params={"basket_id": 1}).json()
    assert listed["total"] == 1

    found = client.get("/reports/search", params={"q": "Tech FR"}).json()
    assert len(found) == 1


def test_create_report_portfolio_wide(client, mock_llm):
    resp = client.post("/reports", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "portfolio"
    assert body["basket_id"] is None


def test_create_report_unknown_basket_returns_404(client, mock_llm):
    resp = client.post("/reports", json={"basket_id": 999})
    assert resp.status_code == 404


def test_mistral_unavailable_returns_503_with_cors_headers(client, monkeypatch):
    """Même piège Starlette que `test_db_unreachable_returns_503_with_cors_headers`,
    pour la classe d'erreur dédiée `MistralUnavailableError` (clé API
    manquante ou quota épuisé) — voir `api/main.py:mistral_exception_handler`."""

    def _raise(*args, **kwargs):
        raise mistral_client.MistralUnavailableError("clé API manquante")

    monkeypatch.setattr(mistral_client, "complete", _raise)

    resp = client.post("/chat", json={"question": "Alpha SA ?"}, headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 503
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
