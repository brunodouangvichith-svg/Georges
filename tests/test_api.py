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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import agents.mistral_client as mistral_client
import api.deps as deps
from api.main import app
from ingestion.models import (
    AgentEvent,
    Basket,
    BasketSecurity,
    CollectedInfoQuarantine,
    Decision,
    DecisionOutcome,
    PatternDetected,
    PriceOHLCV,
    Report,
    Security,
)


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
    # AAA.PA (fixture) monte en continu sur 30 séances -> performance positive
    # sur les trois horizons.
    assert body["performance_1j"] > 0
    assert body["performance_1s"] > 0
    assert body["performance_1m"] > 0


def test_george_index_basket_not_found_returns_404(client):
    resp = client.get("/baskets/999/george-index")
    assert resp.status_code == 404


def test_list_decisions_filtered_by_decision_type(client):
    resp = client.get("/decisions", params={"decision_type": "Achat"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["decision_type"] == "Achat"

    resp = client.get("/decisions", params={"decision_type": "Alléger"})
    assert resp.json()["total"] == 0


def test_list_decisions_filtered_by_lifecycle_status(client):
    resp = client.get("/decisions", params={"status": "confirmee"})
    assert resp.json()["total"] == 1  # la décision de la fixture, rétroactivement "confirmee" (migration 0005)

    resp = client.get("/decisions", params={"status": "proposee"})
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


def test_chat_does_not_false_positive_match_short_symbol_roots_inside_words(client, mock_llm):
    """Régression : `find_relevant_securities` comparait la racine du symbole
    à la question par simple sous-chaîne — une racine courte comme "AC"
    (Accor) apparaît aussi à l'intérieur d'un mot français ordinaire ("ac"
    dans "achat"), reconnaissant à tort un titre sans rapport avec la
    question. Avec la comparaison par frontière de mot (`\\b`), "achat" ne
    doit plus reconnaître "AC.PA", mais "Accor" (le nom complet) le doit
    toujours."""
    with deps.engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [{"symbol": "AC.PA", "name": "Accor", "country": "FR", "currency": "EUR", "sector": "Tourisme", "theme": None}],
        )

    # "Quelles sont les opportunités d'achat ?" bascule sur le rendu
    # déterministe (aucun titre nommé, type "Achat" détecté) — AC.PA n'y
    # figure que s'il a une décision "Achat" ouverte, jamais parce que son
    # symbole apparaîtrait (à tort) dans le mot "achat".
    resp = client.post("/chat", json={"question": "Quelles sont les opportunités d'achat ?"})
    assert "AC.PA" not in resp.json()["answer"]

    resp = client.post("/chat", json={"question": "Que penses-tu d'Accor ?"})
    assert "AC.PA" in resp.json()["answer"]


def test_chat_general_opportunity_question_uses_deterministic_rendering(client, mock_llm):
    """Une question générale sur un type de décision (aucun titre nommé)
    contourne l'appel LLM : `mistral-small-latest` s'est montré peu fiable
    pour énumérer une liste de plusieurs dizaines d'entrées structurées
    (vérifié contre la vraie base — il en omettait la quasi-totalité malgré
    des instructions explicites) — un rendu déterministe en Python élimine
    ce risque plutôt que d'espérer un meilleur prompt."""
    resp = client.post("/chat", json={"question": "Quelles sont les opportunités d'achat en ce moment ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "AAA.PA" in answer
    assert "77.0" in answer
    assert "confirmee" in answer
    # Rendu déterministe, pas un JSON recopié par le LLM factice.
    assert "titres_reconnus" not in answer


def test_chat_general_opportunity_question_with_no_match_says_so(client, mock_llm):
    resp = client.post("/chat", json={"question": "Quelles décisions faut-il surveiller ?"})
    assert resp.status_code == 200
    assert "aucune décision" in resp.json()["answer"].lower()


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


def test_propose_confirm_and_propose_levels_flow(client):
    """Couvre les tâches 1-3 de la Phase 6 : `engine.propose_decisions` crée
    une proposition à partir d'une figure réelle (pas juste `seed_demo.py`),
    ses niveaux sont recalculables avant confirmation, et la confirmation
    fige le statut (l'investisseur peut ajuster les niveaux au passage)."""
    detected_at = pd.Timestamp.now(tz="UTC")
    with deps.engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [{"symbol": "XXX.PA", "name": "Xylo SA", "country": "FR", "currency": "EUR", "sector": "Tech", "theme": None}],
        )
        conn.execute(
            PriceOHLCV.__table__.insert(),
            [
                {
                    "symbol": "XXX.PA",
                    "ts": detected_at,
                    "open": 114.0,
                    "high": 116.0,
                    "low": 113.0,
                    "close": 115.0,
                    "volume": 1_000_000,
                }
            ],
        )
        conn.execute(
            PatternDetected.__table__.insert(),
            [
                {
                    "symbol": "XXX.PA",
                    "pattern_type": "Bull Flag",
                    "detected_at": detected_at,
                    "confidence": 80.0,
                    "context": {
                        "pole_return": 0.1,
                        "pole_amplitude": 10.0,
                        "flag_amplitude": 5.0,
                        "flag_low": 108.0,
                        "flag_high": 113.0,
                    },
                }
            ],
        )

    resp = client.post("/decisions/propose")
    assert resp.status_code == 200
    created = [d for d in resp.json() if d["symbol"] == "XXX.PA"]
    assert len(created) == 1
    decision = created[0]
    assert decision["status"] == "proposee"
    assert decision["decision_type"] == "Achat"  # Bull Flag est une figure haussière
    assert decision["entry_price"] == 115.0
    assert decision["take_profit"] == 125.0  # 115 + pole_amplitude (10.0)
    assert decision["stop_loss"] == pytest.approx(107.78, abs=0.01)  # flag_low (108) * (1 - BREAKOUT_BUFFER)
    decision_id = decision["id"]

    # Une deuxième invocation ne recrée pas de proposition : XXX.PA a déjà
    # une décision ouverte (idempotence de select_candidates).
    resp = client.post("/decisions/propose")
    assert all(d["symbol"] != "XXX.PA" for d in resp.json())

    resp = client.post(f"/decisions/{decision_id}/propose-levels")
    assert resp.status_code == 200
    assert resp.json()["take_profit"] == 125.0

    resp = client.post(f"/decisions/{decision_id}/confirm", json={"stop_loss": 106.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmee"
    assert body["stop_loss"] == 106.0
    assert body["take_profit"] == 125.0  # non fourni dans la requête -> inchangé

    # Ni propose-levels ni confirm ne s'appliquent plus une fois confirmée.
    assert client.post(f"/decisions/{decision_id}/propose-levels").status_code == 409
    assert client.post(f"/decisions/{decision_id}/confirm", json={}).status_code == 409


def test_monitor_and_confirm_exit_flow(client, mock_llm):
    """Couvre les tâches 4-5 de la Phase 6 : le job de suivi détecte un
    stop-loss franchi avec un volume confirmé, propose une sortie totale
    avec justification (Phase 4), et la confirmation clôture réellement la
    décision dans `decision_outcomes`."""
    old_ts = pd.Timestamp("2020-01-01", tz="UTC")
    with deps.engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [{"symbol": "YYY.PA", "name": "Yotta SA", "country": "FR", "currency": "EUR", "sector": "Tech", "theme": None}],
        )
        price_rows = [
            {
                "symbol": "YYY.PA",
                "ts": old_ts + pd.Timedelta(days=i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1_000_000,
            }
            for i in range(20)
        ]
        # Dernière séance : franchissement du stop-loss (90) avec un volume
        # 3x supérieur à la moyenne des 20 séances précédentes -> confirmé.
        price_rows.append(
            {
                "symbol": "YYY.PA",
                "ts": old_ts + pd.Timedelta(days=20),
                "open": 99.0,
                "high": 99.5,
                "low": 85.0,
                "close": 86.0,
                "volume": 3_000_000,
            }
        )
        conn.execute(PriceOHLCV.__table__.insert(), price_rows)
        decision_id = conn.execute(
            Decision.__table__.insert()
            .values(
                symbol="YYY.PA",
                decision_type="Achat",
                status="confirmee",
                entry_price=100.0,
                take_profit=200.0,
                stop_loss=90.0,
                confidence=70.0,
                created_at=old_ts,
            )
            .returning(Decision.id)
        ).scalar_one()

    resp = client.post("/decisions/monitor")
    assert resp.status_code == 200
    proposed = [d for d in resp.json() if d["id"] == decision_id]
    assert len(proposed) == 1
    body = proposed[0]
    assert body["status"] == "sortie_proposee"
    assert body["exit_scenario"] == "sortie_totale"
    assert body["exit_volume_confirmed"] is True
    assert "90.0" in body["exit_justification"]  # contexte réel transmis au LLM (factice) et recopié

    resp = client.post(f"/decisions/{decision_id}/confirm-exit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cloturee"

    with deps.engine.begin() as conn:
        outcome = conn.execute(
            select(DecisionOutcome).where(DecisionOutcome.decision_id == decision_id)
        ).first()
    assert outcome is not None
    assert outcome.result == "stop_loss_hit"
    assert outcome.pnl_pct == pytest.approx(-10.0)

    # Rien à confirmer une deuxième fois.
    assert client.post(f"/decisions/{decision_id}/confirm-exit").status_code == 409


def test_create_and_list_portfolio(client):
    decision_id = _get_decision_id(client)

    resp = client.post("/portfolios", json={"name": "Mon premier portefeuille", "decision_ids": [decision_id]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Mon premier portefeuille"
    assert [d["id"] for d in body["decisions"]] == [decision_id]
    portfolio_id = body["id"]

    resp = client.get("/portfolios")
    assert resp.status_code == 200
    portfolios = resp.json()
    assert any(p["id"] == portfolio_id for p in portfolios)


def test_create_portfolio_rejects_empty_name_or_no_decisions(client):
    decision_id = _get_decision_id(client)
    assert client.post("/portfolios", json={"name": "  ", "decision_ids": [decision_id]}).status_code == 400
    assert client.post("/portfolios", json={"name": "Vide", "decision_ids": []}).status_code == 400


def test_create_portfolio_rejects_unknown_decision_id(client):
    resp = client.post("/portfolios", json={"name": "Test", "decision_ids": [999999]})
    assert resp.status_code == 404


def test_remove_decision_from_portfolio(client):
    decision_id = _get_decision_id(client)
    portfolio_id = client.post(
        "/portfolios", json={"name": "À vider", "decision_ids": [decision_id]}
    ).json()["id"]

    resp = client.delete(f"/portfolios/{portfolio_id}/decisions/{decision_id}")
    assert resp.status_code == 200
    assert resp.json()["decisions"] == []

    assert client.delete(f"/portfolios/{portfolio_id}/decisions/{decision_id}").status_code == 404


def test_delete_portfolio(client):
    decision_id = _get_decision_id(client)
    portfolio_id = client.post(
        "/portfolios", json={"name": "À supprimer", "decision_ids": [decision_id]}
    ).json()["id"]

    assert client.delete(f"/portfolios/{portfolio_id}").status_code == 204
    assert all(p["id"] != portfolio_id for p in client.get("/portfolios").json())
    assert client.delete(f"/portfolios/{portfolio_id}").status_code == 404


def test_allocate_budget_sets_quantities_and_returns_a_deterministic_summary(client):
    decision_id = _get_decision_id(client)
    portfolio_id = client.post("/portfolios", json={"name": "Alloc", "decision_ids": [decision_id]}).json()["id"]

    resp = client.post(f"/portfolios/{portfolio_id}/allocate", json={"budget": 1000.0})
    assert resp.status_code == 200
    body = resp.json()
    decision = body["portfolio"]["decisions"][0]
    # AAA.PA (fixture) entry_price=129.0 -> 1000 // 129.0 = 7 actions.
    assert decision["quantity"] == 7
    assert "AAA.PA" in body["summary"]
    assert "7" in body["summary"]

    # Persisté : une relecture du portefeuille voit la même quantité.
    reread = client.get("/portfolios").json()
    saved = next(p for p in reread if p["id"] == portfolio_id)
    assert saved["decisions"][0]["quantity"] == 7


def test_allocate_budget_rejects_non_positive_budget(client):
    decision_id = _get_decision_id(client)
    portfolio_id = client.post("/portfolios", json={"name": "Alloc2", "decision_ids": [decision_id]}).json()["id"]
    assert client.post(f"/portfolios/{portfolio_id}/allocate", json={"budget": 0}).status_code == 400
    assert client.post(f"/portfolios/{portfolio_id}/allocate", json={"budget": -100}).status_code == 400


def test_allocate_budget_unknown_portfolio_returns_404(client):
    assert client.post("/portfolios/999999/allocate", json={"budget": 1000.0}).status_code == 404


def test_portfolio_decisions_include_current_price_and_pnl(client):
    # created_at explicitement dans le passé (comme test_monitor_and_confirm_exit_flow) :
    # le fixture "AAA.PA" partagé a un created_at = maintenant, plus tardif
    # que sa dernière séance de prix (minuit aujourd'hui), ce qui viderait
    # `since` dans evaluate_decision — un titre dédié évite ce piège.
    old_ts = pd.Timestamp("2020-01-01", tz="UTC")
    with deps.engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [{"symbol": "ZZZ.PA", "name": "Zeta SA", "country": "FR", "currency": "EUR", "sector": "Tech", "theme": None}],
        )
        price_rows = [
            {
                "symbol": "ZZZ.PA",
                "ts": old_ts + pd.Timedelta(days=i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1_000_000,
            }
            for i in range(5)
        ]
        price_rows.append(
            {
                "symbol": "ZZZ.PA",
                "ts": old_ts + pd.Timedelta(days=5),
                "open": 108.0,
                "high": 112.0,
                "low": 107.0,
                "close": 110.0,
                "volume": 1_000_000,
            }
        )
        conn.execute(PriceOHLCV.__table__.insert(), price_rows)
        decision_id = conn.execute(
            Decision.__table__.insert()
            .values(
                symbol="ZZZ.PA",
                decision_type="Achat",
                status="confirmee",
                entry_price=100.0,
                take_profit=200.0,  # volontairement loin : rien n'est "atteint" par ce prix
                stop_loss=50.0,
                confidence=70.0,
                created_at=old_ts,
            )
            .returning(Decision.id)
        ).scalar_one()

    portfolio_id = client.post("/portfolios", json={"name": "PnL test", "decision_ids": [decision_id]}).json()["id"]

    # Sans quantité : le PnL par titre est déjà calculable, pas le total du portefeuille.
    body = client.get("/portfolios").json()
    portfolio = next(p for p in body if p["id"] == portfolio_id)
    decision = portfolio["decisions"][0]
    assert decision["current_price"] == 110.0
    assert decision["pnl_pct"] == pytest.approx(10.0)  # (110 - 100) / 100 * 100
    assert portfolio["total_pnl_amount"] is None  # aucune quantité renseignée encore
    # price_updated_at = date de la dernière séance de prix (2020-01-06),
    # distincte de created_at de la décision (2020-01-01, old_ts).
    assert decision["price_updated_at"].startswith("2020-01-06")
    assert decision["created_at"].startswith("2020-01-01")

    # Avec une quantité (via l'allocation) : le total du portefeuille se calcule.
    client.post(f"/portfolios/{portfolio_id}/allocate", json={"budget": 1000.0})
    body = client.get("/portfolios").json()
    portfolio = next(p for p in body if p["id"] == portfolio_id)
    assert portfolio["total_invested"] == pytest.approx(1000.0)  # 10 actions à 100.0
    assert portfolio["total_pnl_amount"] == pytest.approx(100.0)  # 10 actions x (110 - 100)


def test_refresh_prices_summarizes_updated_and_failed_symbols(client, monkeypatch):
    import api.routers.prices as prices_router

    monkeypatch.setattr(
        prices_router,
        "run_price_refresh",
        lambda: {"AAA.PA": 500, "BBB.PA": 500, "ZZZ.PA": -1},
    )

    response = client.post("/prices/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body == {"total": 3, "updated_count": 2, "failed_symbols": ["ZZZ.PA"]}


def _fake_fred_item(value, label="Taux de change EUR/USD", observed_at="2026-07-27"):
    from agents.orchestrator.types import CollectedItem

    return CollectedItem(label=label, value=value, unit=None, source_name="FRED", source_url="x", observed_at=observed_at)


def _fake_ecb_item(value, label="Taux de change EUR/USD", observed_at="2026-07-27"):
    from agents.orchestrator.types import CollectedItem

    return CollectedItem(label=label, value=value, unit=None, source_name="BCE", source_url="x", observed_at=observed_at)


def test_collect_donnees_macro_writes_validated_events_when_sources_agree(client, monkeypatch):
    import agents.collectors.macro as macro

    monkeypatch.setattr(macro, "fetch_fred_series", lambda *a, **k: _fake_fred_item(1.1385))
    monkeypatch.setattr(macro, "fetch_ecb_series", lambda *a, **k: _fake_ecb_item(1.1377))
    # Frankfurter indisponible dans ce scénario — EUR/GBP et EUR/CHF (source
    # unique Frankfurter) sont donc omis, et EUR/USD ne recoupe que FRED/BCE,
    # gardant les comptes de cette assertion inchangés.
    monkeypatch.setattr(macro, "fetch_frankfurter_rate", lambda *a, **k: None)

    response = client.post("/agents/collect", json={"task_type": "donnees_macro"})
    assert response.status_code == 200
    body = response.json()
    assert body["quarantined_count"] == 0
    assert len(body["validated"]) == 2  # OAT (source unique) + EUR/USD (2 sources concordantes)
    assert all(e["agent_name"] == "donnees_macro" and e["status"] == "validated" for e in body["validated"])

    activity = client.get("/agents/activity", params={"status": "validated"}).json()
    assert any("EUR/USD" in e["description"] for e in activity["items"])


def test_collect_donnees_macro_quarantines_contradictory_sources(client, monkeypatch):
    import agents.collectors.macro as macro

    monkeypatch.setattr(macro, "fetch_fred_series", lambda *a, **k: _fake_fred_item(1.10))
    monkeypatch.setattr(macro, "fetch_ecb_series", lambda *a, **k: _fake_ecb_item(1.30))
    monkeypatch.setattr(macro, "fetch_frankfurter_rate", lambda *a, **k: None)

    response = client.post("/agents/collect", json={"task_type": "donnees_macro"})
    assert response.status_code == 200
    body = response.json()
    assert body["quarantined_count"] == 1
    assert len(body["validated"]) == 1  # seule l'OAT (source unique) est validée

    with deps.engine.begin() as conn:
        rows = conn.execute(select(CollectedInfoQuarantine).where(CollectedInfoQuarantine.task_type == "donnees_macro")).all()
    assert len(rows) == 1
    assert "FRED" in rows[0].reason and "BCE" in rows[0].reason


def test_collect_synthese_document_creates_a_validated_event_from_a_real_report(client, mock_llm):
    report_id = client.post("/reports", json={"basket_id": 1}).json()["id"]

    response = client.post("/agents/collect", json={"task_type": "synthese_document", "report_id": report_id})
    assert response.status_code == 200
    body = response.json()
    assert body["quarantined_count"] == 0
    assert len(body["validated"]) == 1
    event = body["validated"][0]
    assert event["agent_name"] == "synthese_document"
    assert f"#{report_id}" in event["description"]
    # `_fake_complete` renvoie le contexte JSON tel quel : le vrai contenu du
    # rapport (généré par le report_system.txt réel juste au-dessus) doit
    # s'y retrouver, preuve qu'aucun chiffre n'a été inventé en chemin.
    assert "Tech FR" in event["context"]["sources"][0]["value"]


def test_collect_unknown_task_type_returns_400(client):
    response = client.post("/agents/collect", json={"task_type": "presse_sectorielle"})
    assert response.status_code == 400


def test_collect_synthese_document_without_report_id_returns_400(client):
    response = client.post("/agents/collect", json={"task_type": "synthese_document"})
    assert response.status_code == 400


def test_collect_synthese_document_unknown_report_returns_404(client, mock_llm):
    response = client.post("/agents/collect", json={"task_type": "synthese_document", "report_id": 999999})
    assert response.status_code == 404
