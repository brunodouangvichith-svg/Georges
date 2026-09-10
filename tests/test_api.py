"""Tests d'intégration de l'API FastAPI (Phase 3).

Nécessite un démon Docker local (testcontainers lance une instance
Postgres jetable, migrée puis peuplée d'un jeu de données minimal) — voir
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

import agents.company_knowledge as company_knowledge
import agents.external_analysis as external_analysis
import agents.jane_knowledge as jane_knowledge
import agents.mistral_client as mistral_client
import agents.web_search as web_search
import api.auth as auth
import api.deps as deps
from api.main import app
from ingestion.models import (
    AgentEvent,
    Basket,
    BasketSecurity,
    CollectedInfoQuarantine,
    CompanyFundamentals,
    Decision,
    DecisionOutcome,
    Dividend,
    EnergyPriceSnapshot,
    MacroIndicatorSnapshot,
    PatternDetected,
    PriceHistoryLong,
    Report,
    Security,
)


def _fake_complete(system_prompt, user_message, model=None, temperature=0.3, max_retries=3, allow_fallback=True):
    """Remplace `agents.mistral_client.complete` dans les tests : renvoie le
    contexte JSON reçu tel quel plutôt qu'un vrai texte généré, pour vérifier
    (tâche 6 de la Phase 4) que les valeurs numériques réelles transmises en
    contexte se retrouvent bien dans la réponse — sans appel réseau ni clé
    API. Aucun de ces tests n'invente un chiffre : ils vérifient qu'aucun
    n'est perdu en chemin.

    Cas particulier pour `agents.external_analysis.extract_company_name` :
    répond "AUCUNE" (comme si aucune entreprise n'était mentionnée) par
    défaut, pour qu'aucun test n'atteigne par accident un vrai appel réseau
    `yfinance` (`resolve_ticker`/`analyze_ticker`) juste parce qu'il touche
    la branche "titre non reconnu" de `agents.chat.answer_question`. Les
    tests qui veulent exercer l'analyse technique externe mockent
    `external_analysis.extract_company_name`/`resolve_ticker`/
    `analyze_ticker` directement plutôt que de compter sur ce texte-ci."""
    if system_prompt == external_analysis.EXTRACTION_SYSTEM_PROMPT:
        return "AUCUNE"
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
        conn.execute(PriceHistoryLong.__table__.insert(), price_rows)
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
        conn.execute(
            CompanyFundamentals.__table__.insert(),
            [
                # Deux instantanés pour AAA.PA à des dates différentes : sans
                # tri par `observed_at` décroissant, l'endpoint pourrait
                # renvoyer le plus ancien plutôt que le plus récent.
                {
                    "symbol": "AAA.PA",
                    "observed_at": base_ts.date() - pd.Timedelta(days=1),
                    "sector": "Technologie",
                    "industry": "Ancien",
                    "market_cap": 1_000,
                    "trailing_pe": 10.0,
                    "dividend_yield": 1.0,
                    "raw_info": {},
                },
                {
                    "symbol": "AAA.PA",
                    "observed_at": base_ts.date(),
                    "sector": "Technologie",
                    "industry": "Le plus récent",
                    "market_cap": 2_000_000_000,
                    "trailing_pe": 15.5,
                    "dividend_yield": 2.5,
                    "raw_info": {"marketCap": 2_000_000_000},
                },
            ],
        )
        conn.execute(
            Dividend.__table__.insert(),
            [
                {"symbol": "AAA.PA", "ex_date": base_ts.date() - pd.Timedelta(days=10), "amount": 1.5},
                {"symbol": "AAA.PA", "ex_date": base_ts.date(), "amount": 2.0},
            ],
        )
        conn.execute(
            EnergyPriceSnapshot.__table__.insert(),
            [
                # Deux instantanés pour Brent à des dates différentes : sans
                # tri par `snapshot_date` décroissant, l'endpoint pourrait
                # renvoyer l'ancien plutôt que le plus récent.
                {
                    "commodity_code": "BRENT_CRUDE_USD",
                    "price": 88.0,
                    "unit": "barrel",
                    "currency": "USD",
                    "change_24h_pct": 1.0,
                    "snapshot_date": base_ts.date() - pd.Timedelta(days=1),
                },
                {
                    "commodity_code": "BRENT_CRUDE_USD",
                    "price": 91.04,
                    "unit": "barrel",
                    "currency": "USD",
                    "change_24h_pct": 0.0,
                    "snapshot_date": base_ts.date(),
                },
                {
                    "commodity_code": "WTI_USD",
                    "price": 84.67,
                    "unit": "barrel",
                    "currency": "USD",
                    "change_24h_pct": -0.5,
                    "snapshot_date": base_ts.date(),
                },
            ],
        )

    # Ce portail simple (Phase 9) protège chaque routeur via
    # `Depends(require_user)` — aucun des tests existants n'a de jeton
    # Supabase à fournir, donc on contourne la dépendance directement
    # (`app.dependency_overrides`, mécanisme natif de FastAPI, plus propre
    # que monkeypatcher l'appel HTTP à Supabase). `monkeypatch.setitem`
    # s'annule tout seul en fin de test, même style que les
    # `monkeypatch.setattr(deps, ...)` déjà utilisés ci-dessus.
    monkeypatch.setitem(app.dependency_overrides, auth.require_user, lambda: "test-user-id")

    with TestClient(app) as test_client:
        yield test_client

    command.downgrade(cfg, "base")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_news_maps_the_real_yfinance_shape(client, monkeypatch):
    import api.routers.news as news

    class _FakeTicker:
        news = [
            {
                "content": {
                    "title": "FTSE 100 sets new record",
                    "provider": {"displayName": "PA Media: Money"},
                    "pubDate": "2026-07-29T16:45:52Z",
                    "canonicalUrl": {"url": "https://example.test/a"},
                }
            },
            # Un item sans titre exploitable doit être ignoré, pas planter.
            {"content": {"title": None}},
        ]

    monkeypatch.setattr(news.yf, "Ticker", lambda symbol: _FakeTicker())

    resp = client.get("/news")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "FTSE 100 sets new record"
    assert body[0]["source_name"] == "PA Media: Money"


def test_list_news_returns_empty_list_on_yfinance_failure(client, monkeypatch):
    import api.routers.news as news

    def _raise(symbol):
        raise RuntimeError("boom")

    monkeypatch.setattr(news.yf, "Ticker", _raise)

    resp = client.get("/news")
    assert resp.status_code == 200
    assert resp.json() == []


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


def test_get_security_fundamentals_returns_most_recent_snapshot(client):
    resp = client.get("/securities/AAA.PA/fundamentals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["industry"] == "Le plus récent"
    assert body["market_cap"] == 2_000_000_000
    assert body["trailing_pe"] == 15.5


def test_get_security_fundamentals_404_when_no_snapshot_yet(client):
    resp = client.get("/securities/BBB.PA/fundamentals")
    assert resp.status_code == 404


def test_list_security_dividends_most_recent_first(client):
    resp = client.get("/securities/AAA.PA/dividends")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["items"][0]["amount"] == 2.0


def test_list_energy_prices_returns_most_recent_snapshot_per_commodity(client):
    resp = client.get("/energy-prices")
    assert resp.status_code == 200
    body = resp.json()
    by_code = {row["commodity_code"]: row for row in body}
    assert len(body) == 2  # BRENT_CRUDE_USD + WTI_USD, une ligne chacun
    assert by_code["BRENT_CRUDE_USD"]["price"] == 91.04  # le plus récent, pas 88.0
    assert by_code["WTI_USD"]["price"] == 84.67


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
    monkeypatch.setitem(app.dependency_overrides, auth.require_user, lambda: "test-user-id")

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
    # `fondamentaux` doit être présent avec les données réelles les plus
    # récentes du fixture partagé (deux instantanés insérés pour AAA.PA plus
    # haut ; le plus ancien, "industry": "Ancien", ne doit pas apparaître).
    assert '"activite": null' in answer
    assert "Le plus récent" in answer
    assert "Ancien" not in answer


def test_chat_includes_fundamentals_when_available(client, mock_llm):
    with deps.engine.begin() as conn:
        conn.execute(
            CompanyFundamentals.__table__.insert(),
            [
                {
                    "symbol": "AAA.PA",
                    "observed_at": pd.Timestamp.now(tz="UTC").date(),
                    "sector": "Technology",
                    "industry": "Software",
                    "long_business_summary": "Alpha SA développe des logiciels.",
                    "market_cap": 1_000_000,
                    "raw_info": {},
                }
            ],
        )
    resp = client.post("/chat", json={"question": "Que penses-tu de Alpha SA ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "Alpha SA développe des logiciels." in answer
    assert "Software" in answer


def test_chat_with_no_recognized_security_says_so_via_empty_context(client, mock_llm):
    resp = client.post("/chat", json={"question": "Quelle est la météo à Paris ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert '"titres_reconnus": []' in answer
    assert '"actualites_recentes": []' in answer
    assert '"resultats_web": []' in answer


def test_chat_teach_intent_stores_knowledge_without_calling_the_llm(client, mock_llm):
    """"apprends sur le tas" (demandé directement par l'utilisateur) : une
    question du type "ajoute à tes skills cette information : <contenu>"
    doit persister `<contenu>` dans `jane_knowledge` et répondre par une
    confirmation déterministe — jamais un texte généré par le LLM (vérifié
    ici en s'assurant que la réponse ne contient pas le marqueur
    `[modèle]` qu'ajoute `_fake_complete`)."""
    resp = client.post(
        "/chat",
        json={"question": "Ajoute à tes skills cette information : Pappers.fr est utile pour les bilans d'entreprises françaises."},
    )
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert answer == "C'est noté, j'ai ajouté cette information à mes connaissances."
    assert "[" not in answer  # pas le marqueur `[model]` de `_fake_complete` : aucun appel LLM sur ce chemin

    with deps.SessionLocal() as db:
        entries = jane_knowledge.search_jane_knowledge(db, "Pappers.fr", limit=5)
    assert len(entries) == 1
    assert entries[0].content == "Pappers.fr est utile pour les bilans d'entreprises françaises."
    assert entries[0].source_name == "Enseigné via /chat"


def test_chat_teach_intent_ignores_a_colon_without_a_teaching_keyword(client, mock_llm):
    """Une question contenant ":" mais aucun mot-clé d'intention
    (`TEACH_INTENT_KEYWORDS`) doit suivre le chemin normal — sinon toute
    question un peu structurée ("horaires : quand ouvre la Bourse de Paris
    ?") serait interprétée à tort comme un enseignement."""
    resp = client.post("/chat", json={"question": "Horaires : quand ouvre la Bourse de Paris ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert answer != "C'est noté, j'ai ajouté cette information à mes connaissances."

    with deps.SessionLocal() as db:
        entries = jane_knowledge.search_jane_knowledge(db, "Bourse de Paris", limit=5)
    assert entries == []


def test_chat_teach_intent_requires_a_word_boundary_match(client, mock_llm):
    """Régression trouvée en `/code-review` : `TEACH_INTENT_KEYWORDS` ("ajoute"
    notamment) matchait par simple sous-chaîne, sans frontière de mot — même
    piège déjà rencontré deux fois dans ce fichier pour
    `find_relevant_securities` (voir sa docstring). Une vraie question
    financière contenant "ajoute" avant ":" était donc avalée à tort comme un
    enseignement au lieu d'être répondue."""
    resp = client.post(
        "/chat",
        json={"question": "Un investisseur ajoute des actions Alpha SA à son portefeuille : quel est l'impact sur le George Index ?"},
    )
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert answer != "C'est noté, j'ai ajouté cette information à mes connaissances."
    assert "AAA.PA" in answer  # la vraie question a bien été traitée normalement (titre reconnu)


def test_chat_teach_intent_degrades_gracefully_when_mistral_is_unavailable(client, mock_llm, monkeypatch):
    """Régression trouvée en `/code-review` : `add_knowledge` embedde via
    Mistral avant d'écrire, sans le même filet `MistralUnavailableError` que
    le reste de ce fichier (ex. `learned_knowledge` juste en dessous) —
    seul chemin qui remontait une 503 brute plutôt que de dégrader."""

    def _fail(texts, model=None):
        raise mistral_client.MistralUnavailableError("indisponible")

    monkeypatch.setattr(mistral_client, "embed", _fail)
    resp = client.post("/chat", json={"question": "Ajoute à tes skills cette information : Pappers.fr est utile."})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Je n'ai pas pu enregistrer cette information pour le moment, réessaie un peu plus tard."


def test_chat_teach_intent_reports_when_content_is_already_known(client, mock_llm, monkeypatch):
    """Deux enseignements de contenu identique (même texte -> même vecteur
    d'embedding avec ce faux `embed`) doivent dédupliquer, même principe que
    `tests/test_jane_knowledge.py:test_add_knowledge_skips_near_duplicate_content` :
    `mock_llm` seul ne convient pas ici (`_fake_embed` renvoie un vecteur nul
    identique pour tout texte, ce qui empêcherait de distinguer un vrai
    doublon d'un contenu different)."""

    def _distinct_vector_embed(texts, model=None):
        from ingestion.models import EMBEDDING_DIM

        return [[1.0] + [0.0] * (EMBEDDING_DIM - 1) if "Pappers" in text else [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2) for text in texts]

    monkeypatch.setattr(mistral_client, "embed", _distinct_vector_embed)

    first = client.post("/chat", json={"question": "Retiens ceci : Pappers.fr est utile pour les bilans."})
    assert first.json()["answer"] == "C'est noté, j'ai ajouté cette information à mes connaissances."

    duplicate = client.post("/chat", json={"question": "Retiens ceci : Pappers.fr est utile pour les bilans."})
    assert duplicate.json()["answer"] == "C'est déjà dans mes connaissances, je n'ai rien ajouté de nouveau."

    with deps.SessionLocal() as db:
        entries = jane_knowledge.search_jane_knowledge(db, "Pappers.fr est utile pour les bilans.", limit=5)
    assert len(entries) == 1


def test_chat_includes_previously_taught_knowledge_in_later_answers(client, mock_llm, monkeypatch):
    """Une connaissance enseignée doit être réutilisable pour toute question
    ultérieure, pas seulement au moment de l'enseignement — demandé
    directement par l'utilisateur ("to learn on the go")."""

    def _distinct_vector_embed(texts, model=None):
        from ingestion.models import EMBEDDING_DIM

        return [[1.0] + [0.0] * (EMBEDDING_DIM - 1) for _ in texts]

    monkeypatch.setattr(mistral_client, "embed", _distinct_vector_embed)

    teach = client.post(
        "/chat", json={"question": "Ajoute à tes skills cette information : Zonebourse.com est utile pour le consensus analystes."}
    )
    assert teach.json()["answer"] == "C'est noté, j'ai ajouté cette information à mes connaissances."

    resp = client.post("/chat", json={"question": "Où trouver le consensus des analystes ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "Zonebourse.com est utile pour le consensus analystes." in answer


def test_chat_enriches_a_tracked_security_with_recent_company_news(client, mock_llm, monkeypatch):
    """`company_news_knowledge` (alimentée par `agents/george_veille.py`) est
    une simple requête DB filtrée par récence, pas un appel réseau — on la
    mocke directement au niveau de `agents.company_knowledge` plutôt que de
    seeder une vraie ligne avec un embedding factice."""
    entry = type(
        "FakeEntry", (), {"content": "Alpha SA a publié des résultats en hausse.", "source_name": "Reuters", "source_url": "https://reuters.com/alpha"}
    )()
    monkeypatch.setattr(
        company_knowledge,
        "get_recent_company_knowledge",
        lambda db, symbol=None, company_name=None, limit=3: [entry] if symbol == "AAA.PA" else [],
    )
    resp = client.post("/chat", json={"question": "Que penses-tu de Alpha SA ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "Alpha SA a publié des résultats en hausse." in answer
    assert "https://reuters.com/alpha" in answer


def test_chat_finds_biofuel_company_knowledge_before_live_web_search(client, mock_llm, monkeypatch):
    """Une entreprise du secteur biocarburants/gaz renouvelables déjà
    couverte par `agents/george_veille.py` doit être répondue depuis
    `company_news_knowledge`, sans jamais appeler `agents.web_search` en
    direct."""
    entry = type(
        "FakeEntry", (), {"content": "Neste annonce un investissement dans une nouvelle raffinerie.", "source_name": "Reuters", "source_url": "https://reuters.com/neste"}
    )()
    monkeypatch.setattr(
        company_knowledge,
        "get_recent_company_knowledge",
        lambda db, symbol=None, company_name=None, limit=3: [entry] if company_name == "Neste" else [],
    )
    # `biofuel_company` ("Neste") est déjà connu ici, donc
    # `external_analysis.extract_company_name` n'est jamais appelée (voir
    # `agents.chat.answer_question`) -- `resolve_ticker` le serait, pour de
    # vrai contre yfinance, sans ce mock.
    monkeypatch.setattr(external_analysis, "resolve_ticker", lambda company_name: None)

    def _fail_if_called(*a, **k):
        raise AssertionError("agents.web_search.search ne doit pas être appelé quand company_news_knowledge a déjà une entrée")

    monkeypatch.setattr(web_search, "search", _fail_if_called)

    resp = client.post("/chat", json={"question": "Des nouvelles de Neste ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "Neste annonce un investissement dans une nouvelle raffinerie." in answer
    assert '"resultats_web": []' in answer


def test_chat_runs_live_technical_analysis_for_any_mentioned_company(client, mock_llm, monkeypatch):
    """Demandé directement par l'utilisateur : "n'importe quelle entreprise
    mentionnée dans le chat" doit pouvoir recevoir une vraie analyse
    technique (10 ans, yfinance), pas seulement un résumé d'actualité web.
    `extract_company_name`/`resolve_ticker`/`analyze_ticker` mockés
    directement -- ce test vérifie le câblage dans `answer_question`, pas
    `agents/external_analysis.py` lui-même (voir `test_external_analysis.py`)."""
    monkeypatch.setattr(external_analysis, "extract_company_name", lambda question: "Haffner Energy")
    monkeypatch.setattr(external_analysis, "resolve_ticker", lambda company_name: "ALHAF.PA")

    match = type(
        "FakeMatch",
        (),
        {
            "pattern_type": "Double Bottom",
            "confidence": 62.5,
            "detected_at": pd.Timestamp("2026-08-15", tz="UTC"),
        },
    )()
    monkeypatch.setattr(external_analysis, "analyze_ticker", lambda ticker: match)
    monkeypatch.setattr(web_search, "search", lambda query, max_results=web_search.MAX_RESULTS: [])

    resp = client.post("/chat", json={"question": "que penses-tu de Haffner Energy ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert '"ticker": "ALHAF.PA"' in answer
    assert '"figure": "Double Bottom"' in answer
    assert '"confiance": 62.5' in answer


def test_chat_falls_back_to_web_search_for_a_security_outside_the_tracked_universe(client, mock_llm, monkeypatch):
    """Une société hors du référentiel suivi (~120 valeurs CAC 40/Mid 60) --
    `find_relevant_securities` ne reconnaît rien, donc `answer_question` doit
    interroger `agents.web_search` et fournir les résultats à George en plus
    de `titres_reconnus` (vide)."""
    monkeypatch.setattr(
        web_search,
        "search",
        lambda query, max_results=web_search.MAX_RESULTS: [
            {"titre": "Apple Inc. (AAPL)", "extrait": "Apple est une société technologique américaine...", "url": "https://example.com/aapl"}
        ],
    )
    resp = client.post("/chat", json={"question": "Que penses-tu d'Apple ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert '"titres_reconnus": []' in answer
    assert "Apple Inc. (AAPL)" in answer
    assert "https://example.com/aapl" in answer


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


def test_chat_does_not_false_positive_match_short_names_inside_words(client, mock_llm, monkeypatch):
    """Régression trouvée en direct via l'app (7 sept. 2026) : contrairement
    au symbole (déjà protégé par une frontière de mot, voir le test
    ci-dessus), `find_relevant_securities` comparait le NOM complet à la
    question par simple sous-chaîne — un nom aussi court que "SES" (SESG.PA)
    apparaît aussi à l'intérieur d'un mot français ordinaire ("ses" dans
    "penses"), reconnaissant à tort un titre sans rapport. Conséquence
    concrète observée : `titres_reconnus` non vide court-circuitait
    entièrement le repli `company_news_knowledge`/recherche web prévu pour
    une société hors référentiel — "que penses-tu de Haffner ?" ne cherchait
    alors jamais "Haffner" nulle part. Avec la frontière de mot, "SES" ne
    doit plus être reconnu ici, et la recherche web doit être atteinte."""
    with deps.engine.begin() as conn:
        conn.execute(
            Security.__table__.insert(),
            [{"symbol": "SESG.PA", "name": "SES", "country": "LU", "currency": "EUR", "sector": "Télécommunications", "theme": None}],
        )
    monkeypatch.setattr(
        web_search,
        "search",
        lambda query, max_results=web_search.MAX_RESULTS: [
            {"titre": "Haffner Energy", "extrait": "...", "url": "https://example.com/haffner"}
        ],
    )

    resp = client.post("/chat", json={"question": "que penses tu de Haffner ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "SESG.PA" not in answer
    assert "Haffner Energy" in answer


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


def test_decision_explanation_is_reformulated_by_jane(client, mock_llm):
    """`explanation` passe toujours par `agents.jane.reformulate_formal`
    (une passe de style demandée par l'utilisateur pour l'écran « George
    explique », sans rapport avec le second avis de `second_opinion`
    ci-dessous) -- le client Mistral factice imbrique le texte précédent
    dans son "echo", donc le tag de modèle de George doit apparaître deux
    fois (l'explication brute, puis la reformulation) sans qu'aucun chiffre
    réel ne soit perdu au passage."""
    decision_id = _get_decision_id(client)
    resp = client.post(f"/decisions/{decision_id}/explanation", json={"include_second_opinion": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["explanation"].count("mistral-small-latest") == 2
    assert "129.0" in body["explanation"]
    assert body["second_opinion"] is None


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


def test_second_opinions_are_persisted_and_listed_most_recent_first(client, mock_llm):
    """Chaque appel avec `include_second_opinion=True` doit désormais écrire
    une ligne dans `jane_second_opinions` (jusqu'ici générée à la volée et
    jamais conservée) — vérifié ici en bout en bout via l'endpoint de
    lecture plutôt qu'en inspectant la base directement."""
    decision_id = _get_decision_id(client)

    first = client.post(f"/decisions/{decision_id}/explanation", json={"include_second_opinion": True})
    second = client.post(f"/decisions/{decision_id}/explanation", json={"include_second_opinion": True})
    assert first.status_code == 200 and second.status_code == 200

    resp = client.get(f"/decisions/{decision_id}/second-opinions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    # Les deux appels renvoient le même texte factice (`_fake_complete` échote
    # le contexte reçu) -- le point vérifié ici est bien la persistance et
    # l'ordre (plus récent en premier), pas le contenu du texte lui-même.
    assert body["items"][0]["content"] == first.json()["second_opinion"]
    assert body["items"][0]["decision_id"] == decision_id
    assert body["items"][0]["created_at"] >= body["items"][1]["created_at"]


def test_second_opinions_list_is_empty_when_never_requested(client):
    decision_id = _get_decision_id(client)
    resp = client.get(f"/decisions/{decision_id}/second-opinions")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_second_opinions_unknown_decision_returns_404(client):
    resp = client.get("/decisions/999999/second-opinions")
    assert resp.status_code == 404


def test_ask_jane_answers_via_janes_own_model(client, mock_llm):
    """Bouton flottant « Ask Jane » de l'écran Univers mobile — vérifie que
    la question posée atteint bien le LLM et que c'est Jane (`mistral-large-
    latest`), pas George, qui répond."""
    resp = client.post("/jane/ask", json={"question": "Qu'est-ce que le ratio de Sharpe ?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "mistral-large-latest" in body["answer"]
    assert "ratio de Sharpe" in body["answer"]


def test_ask_jane_with_no_indexed_knowledge_still_answers(client, mock_llm):
    """Aucune connaissance indexée dans cette base de test fraîche —
    `connaissances_pertinentes` doit malgré tout atteindre le LLM, vide
    plutôt que de faire échouer l'appel. `TAVILY_API_KEY` n'est pas
    configurée dans cet environnement de test, donc `resultats_web` est vide
    aussi (repli web silencieusement inactif, pas d'appel réseau)."""
    resp = client.post("/jane/ask", json={"question": "Question hors sujet"})
    assert resp.status_code == 200
    assert '"connaissances_pertinentes": []' in resp.json()["answer"]
    assert '"resultats_web": []' in resp.json()["answer"]


def test_ask_jane_falls_back_to_web_search_results(client, mock_llm, monkeypatch):
    """Avec `TAVILY_API_KEY` configurée, `agents.jane.ask` doit fournir les
    résultats web au LLM en plus de `connaissances_pertinentes` — c'est au
    prompt système, pas à Python, de choisir laquelle des deux sources
    utiliser (voir `agents/jane.py:ask`, `jane_knowledge.search_jane_knowledge`
    n'a pas de seuil de pertinence)."""
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(
        web_search,
        "search",
        lambda query, max_results=web_search.MAX_RESULTS: [
            {"titre": "MACD (Investopedia)", "extrait": "Moving average convergence/divergence...", "url": "https://example.com/macd"}
        ],
    )
    resp = client.post("/jane/ask", json={"question": "Qu'est-ce que le MACD ?"})
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "MACD (Investopedia)" in answer
    assert "https://example.com/macd" in answer


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
            PriceHistoryLong.__table__.insert(),
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
        conn.execute(PriceHistoryLong.__table__.insert(), price_rows)
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
        conn.execute(PriceHistoryLong.__table__.insert(), price_rows)
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
    # day_change_pct compare aux deux dernières séances (100.0 puis 110.0),
    # pas à entry_price -- non ajusté à la direction, contrairement à pnl_pct.
    assert decision["day_change_pct"] == pytest.approx(10.0)  # (110 - 100) / 100 * 100
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


def test_refresh_prices_runs_in_background_and_reports_final_status_via_polling(client, monkeypatch):
    import api.routers.prices as prices_router

    monkeypatch.setattr(prices_router, "_state", {"status": "idle"})
    monkeypatch.setattr(
        prices_router,
        "run_price_refresh",
        lambda: {"AAA.PA": 500, "BBB.PA": 500, "ZZZ.PA": -1},
    )

    # TestClient exécute les BackgroundTasks de façon synchrone avant de
    # rendre la main (voir docs FastAPI sur le test des tâches de fond) : le
    # job a donc déjà tourné au moment où ce POST revient, mais sa propre
    # réponse reste celle construite *avant* la planification de la tâche.
    trigger_response = client.post("/prices/refresh")
    assert trigger_response.status_code == 200
    assert trigger_response.json()["status"] == "running"

    status_response = client.get("/prices/refresh")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "done"
    assert body["total"] == 3
    assert body["updated_count"] == 2
    assert body["failed_symbols"] == ["ZZZ.PA"]


def test_refresh_prices_is_idempotent_while_a_job_is_already_running(client, monkeypatch):
    import api.routers.prices as prices_router

    calls = []
    monkeypatch.setattr(prices_router, "_state", {"status": "running", "started_at": None})
    monkeypatch.setattr(prices_router, "run_price_refresh", lambda: calls.append(1) or {})

    response = client.post("/prices/refresh")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert calls == []  # pas de second job déclenché en parallèle


def test_refresh_prices_reports_failed_status_on_exception(client, monkeypatch):
    import api.routers.prices as prices_router

    def _boom():
        raise RuntimeError("yfinance indisponible")

    monkeypatch.setattr(prices_router, "_state", {"status": "idle"})
    monkeypatch.setattr(prices_router, "run_price_refresh", _boom)

    client.post("/prices/refresh")

    body = client.get("/prices/refresh").json()
    assert body["status"] == "failed"
    assert body["error"] == "yfinance indisponible"


def test_refresh_prices_status_is_idle_before_any_trigger(client, monkeypatch):
    import api.routers.prices as prices_router

    monkeypatch.setattr(prices_router, "_state", {"status": "idle"})

    body = client.get("/prices/refresh").json()
    assert body["status"] == "idle"
    assert body["total"] is None


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

    # Un instantané par source, pas juste un par indicateur (EUR/USD a 2
    # sources ici) — voir agents/orchestrator/run.py:_upsert_indicator_snapshots.
    with deps.engine.begin() as conn:
        rows = conn.execute(
            select(MacroIndicatorSnapshot).where(MacroIndicatorSnapshot.indicator == "Taux de change EUR/USD")
        ).all()
    assert {r.source_name for r in rows} == {"FRED", "BCE"}
    assert {float(r.value) for r in rows} == {1.1385, 1.1377}


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

    # Une donnée contradictoire ne doit jamais entrer dans
    # macro_indicator_snapshots, seulement dans collected_info_quarantine.
    with deps.engine.begin() as conn:
        snapshot_rows = conn.execute(
            select(MacroIndicatorSnapshot).where(MacroIndicatorSnapshot.indicator == "Taux de change EUR/USD")
        ).all()
    assert snapshot_rows == []


def test_collect_donnees_eurostat_writes_indicator_snapshots(client, monkeypatch):
    """Couvre le même chemin d'écriture (`run_collection_task`) sur un
    `task_type` différent de `donnees_macro`, pour confirmer que ce n'est
    pas câblé en dur pour un seul sous-agent."""
    import agents.collectors.eurostat as eurostat

    def _fake_eurostat_item(dataset, geo_code, params, label, source_name, unit):
        from agents.orchestrator.types import CollectedItem

        value = 6.2 if "chômage" in label.lower() else 2.1
        return CollectedItem(
            label=label, value=value, unit=unit, source_name=source_name, source_url="x", observed_at="2026-06"
        )

    monkeypatch.setattr(eurostat, "fetch_eurostat_series", _fake_eurostat_item)

    response = client.post("/agents/collect", json={"task_type": "donnees_eurostat"})
    assert response.status_code == 200
    body = response.json()
    assert body["quarantined_count"] == 0
    assert len(body["validated"]) == 2  # chômage + inflation, chacun source unique

    with deps.engine.begin() as conn:
        rows = conn.execute(
            select(MacroIndicatorSnapshot).where(MacroIndicatorSnapshot.source_name == "Eurostat")
        ).all()
    assert len(rows) == 2
    assert {r.indicator for r in rows} == {"Taux de chômage (zone euro)", "Inflation HICP (zone euro)"}


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


def test_share_email_with_known_symbol_attaches_chart(client, mock_llm, monkeypatch):
    import notifications.email_client as email_client

    captured = {}
    monkeypatch.setattr(
        email_client,
        "send_email",
        lambda **kwargs: captured.update(kwargs),
    )

    response = client.post(
        "/share/email",
        json={"to_email": "investisseur@example.com", "subject": "George explique", "text": "Contenu réel.", "symbol": "AAA.PA"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"sent": True, "chart_attached": True}
    assert captured["to_email"] == "investisseur@example.com"
    assert captured["attachment_bytes"] is not None
    assert captured["attachment_filename"] == "AAA.PA.png"


def test_share_email_without_symbol_sends_text_only(client, mock_llm, monkeypatch):
    import notifications.email_client as email_client

    captured = {}
    monkeypatch.setattr(email_client, "send_email", lambda **kwargs: captured.update(kwargs))

    response = client.post("/share/email", json={"to_email": "investisseur@example.com", "subject": "Sujet", "text": "Texte."})
    assert response.status_code == 200
    assert response.json() == {"sent": True, "chart_attached": False}
    assert captured["attachment_bytes"] is None


def test_share_email_with_symbol_without_price_history_sends_without_chart(client, mock_llm, monkeypatch):
    import notifications.email_client as email_client

    captured = {}
    monkeypatch.setattr(email_client, "send_email", lambda **kwargs: captured.update(kwargs))

    response = client.post(
        "/share/email",
        json={"to_email": "investisseur@example.com", "subject": "Sujet", "text": "Texte.", "symbol": "INCONNU.PA"},
    )
    assert response.status_code == 200
    assert response.json() == {"sent": True, "chart_attached": False}
    assert captured["attachment_bytes"] is None


def test_share_email_reformulates_text_via_mistral(client, mock_llm, monkeypatch):
    """`mock_llm` remplace `mistral_client.complete` par `_fake_complete`
    (renvoie le contexte reçu, préfixé du modèle) -- confirme que le texte
    envoyé par email est bien passé par la reformulation, pas le texte brut
    tel quel."""
    import notifications.email_client as email_client

    captured = {}
    monkeypatch.setattr(email_client, "send_email", lambda **kwargs: captured.update(kwargs))

    response = client.post("/share/email", json={"to_email": "investisseur@example.com", "subject": "Sujet", "text": "Texte brut original."})
    assert response.status_code == 200
    assert "Texte brut original." in captured["text"]  # _fake_complete échote le message reçu
    assert captured["text"] != "Texte brut original."  # mais préfixé -- prouve que la reformulation a bien été appelée


def test_share_email_service_unavailable_returns_503_with_cors_headers(client, mock_llm, monkeypatch):
    import notifications.email_client as email_client

    def _raise(**kwargs):
        raise email_client.EmailUnavailableError("clé RESEND_API_KEY manquante")

    monkeypatch.setattr(email_client, "send_email", _raise)

    response = client.post(
        "/share/email",
        json={"to_email": "investisseur@example.com", "subject": "Sujet", "text": "Texte."},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 503
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
