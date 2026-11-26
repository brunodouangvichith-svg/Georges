"""`agents/strategic_report.py` — parties pures (calculs, contexte LLM,
sources web, repli LLM) et endpoints de génération. Réseau, LLM et base mockés."""

import datetime

import pytest

from agents import mistral_client, strategic_report, web_search


def _context():
    return {
        "securities": [
            {"symbol": "AIR.PA", "name": "Airbus", "sector": "Industrie"},
            {"symbol": "MC.PA", "name": "LVMH", "sector": "Luxe"},
            {"symbol": "BNP.PA", "name": "BNP Paribas", "sector": "Banque"},
        ],
        "decisions": {
            "AIR.PA": {"decision_type": "Achat", "confidence": 80.0, "pattern_type": "Double Bottom"},
            "MC.PA": {"decision_type": "Alléger", "confidence": 70.0, "pattern_type": "Double Top"},
        },
        "prices": {
            "AIR.PA": {"close": 200.0, "as_of": "2026-10-15", "week_change_pct": 2.5},
            "MC.PA": {"close": 400.0, "as_of": "2026-10-15", "week_change_pct": -3.0},
            "BNP.PA": {"close": 90.0, "as_of": "2026-10-15", "week_change_pct": None},
        },
        "bonds": {
            "cards": [
                {"instrument": "OAT_FR_10Y", "value_pct": 4.48, "observed_at": "2026-09-01"},
                {"instrument": "BUND_DE_10Y", "value_pct": 3.47, "observed_at": "2026-09-01"},
            ],
            "spread_oat_bund_bps": 101.0,
            "us_curve_slope_bps": 37.0,
        },
        "energy": [],
        "geopolitics_france": [],
    }


def test_compute_risk_uses_oat_and_spread():
    risk = strategic_report.compute_risk(_context()["bonds"])
    assert risk["level"] == "vert"
    assert risk["oat_10y_pct"] == 4.48 and risk["spread_oat_bund_bps"] == 101.0
    assert "rouge" in risk["criteria"]


def test_compute_risk_is_undetermined_without_bond_data():
    assert strategic_report.compute_risk({"cards": [], "spread_oat_bund_bps": None})["level"] == "indetermine"


def test_exit_and_closed_decisions_are_not_labelled_as_buys():
    """Régression : monitor_decisions passe le statut à `sortie_proposee` sans
    changer `decision_type` ("Achat") — ce n'est pas un achat."""
    assert strategic_report.decision_label({"decision_type": "Achat", "status": "sortie_proposee"}) == "Sortie proposée"
    assert strategic_report.decision_label({"decision_type": "Achat", "status": "cloturee"}) == "Clôturée"
    assert strategic_report.decision_label({"decision_type": "Achat", "status": "proposee"}) == "Achat"


def test_recent_closes_computes_the_weekly_change():
    import types

    rows = [("A", datetime.datetime(2026, 10, d), 10.0 + d) for d in range(1, 16)]
    fake_db = types.SimpleNamespace(execute=lambda stmt: rows)
    result = strategic_report._recent_closes(fake_db, ["A"], datetime.date(2026, 10, 16))
    assert result["A"]["close"] == 25.0 and result["A"]["week_change_pct"] == 25.0


def test_cac40_table_has_every_security():
    table = strategic_report.build_cac40_table(_context())
    assert [r["symbol"] for r in table] == ["AIR.PA", "MC.PA", "BNP.PA"]
    assert table[0]["decision_type"] == "Achat" and table[2]["decision_type"] is None
    assert "portfolio_action" not in table[0]


def test_llm_context_groups_decisions_without_any_virtual_portfolio():
    context = _context()
    data = {
        "report_date": "2026-10-16",
        "risk": strategic_report.compute_risk(context["bonds"]),
        "bonds": context["bonds"],
        "energy": [],
        "cac40_index": None,
        "geopolitics_france": [],
        "sources": [],
        "cac40": strategic_report.build_cac40_table(context),
    }
    llm = strategic_report.build_llm_context(data)
    assert llm["decisions_george_par_type"]["Aucune décision ouverte"] == ["BNP Paribas"]
    assert llm["plus_fortes_baisses_5_seances"][0] == {"valeur": "LVMH", "variation_pct": -3.0}
    assert "portefeuille_virtuel" not in llm
    assert "portefeuille virtuel" not in mistral_client.load_system_prompt(strategic_report.PROMPT_NAME).lower()


def test_fetch_web_sources_numbers_and_dedupes(monkeypatch):
    calls = []

    def fake_search(query, max_results=5, days=None):
        calls.append(days)
        return [{"titre": "Même article", "extrait": "x" * 5000, "url": "https://ex.com/a"}]

    monkeypatch.setattr(web_search, "search", fake_search)
    sources = strategic_report.fetch_web_sources()
    assert len(sources) == 1 and sources[0]["n"] == 1
    assert len(sources[0]["extrait"]) == strategic_report.WEB_EXTRACT_MAX_CHARS
    assert set(calls) == {strategic_report.WEB_NEWS_DAYS}


def test_fetch_web_sources_skips_failing_queries(monkeypatch):
    def failing(query, max_results=5, days=None):
        raise web_search.WebSearchUnavailableError("down")

    monkeypatch.setattr(web_search, "search", failing)
    assert strategic_report.fetch_web_sources() == []


def test_write_narrative_falls_back_when_llm_is_down(monkeypatch):
    def down(*args, **kwargs):
        raise mistral_client.MistralUnavailableError("down")

    monkeypatch.setattr(mistral_client, "complete", down)
    text, model = strategic_report.write_narrative({"x": 1})
    assert text == strategic_report.FALLBACK_NARRATIVE and model is None


def test_generation_endpoint_runs_job_and_reports_status(monkeypatch):
    from fastapi.testclient import TestClient

    from api import auth
    from api.main import app
    from api.routers import strategic_reports

    monkeypatch.setitem(app.dependency_overrides, auth.require_user, lambda: "test-user-id")
    monkeypatch.setattr(strategic_reports, "_state", {"status": "idle"})
    monkeypatch.setattr(strategic_report, "generate_report", lambda session_factory, now=None: 42)
    client = TestClient(app)

    started = client.post("/strategic-reports/generate")
    assert started.status_code == 200 and started.json()["status"] == "running"
    # TestClient exécute les BackgroundTasks avant de rendre la main.
    status = client.get("/strategic-reports/generate").json()
    assert status["status"] == "done" and status["report_id"] == 42


def test_generation_endpoint_surfaces_job_failure(monkeypatch):
    from fastapi.testclient import TestClient

    from api import auth
    from api.main import app
    from api.routers import strategic_reports

    def boom(session_factory, now=None):
        raise RuntimeError("base indisponible")

    monkeypatch.setitem(app.dependency_overrides, auth.require_user, lambda: "test-user-id")
    monkeypatch.setattr(strategic_reports, "_state", {"status": "idle"})
    monkeypatch.setattr(strategic_report, "generate_report", boom)
    client = TestClient(app)
    client.post("/strategic-reports/generate")
    status = client.get("/strategic-reports/generate").json()
    assert status["status"] == "failed" and "base indisponible" in status["error"]


# --- Génération complète contre une vraie base (Docker / testcontainers) ---


def test_generate_report_end_to_end(database_url, monkeypatch):
    """Deux générations successives : les rapports sont écrits sans aucun ordre
    simulé, et l'API sert le dernier."""
    import pandas as pd
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import sessionmaker

    from api import auth, deps
    from api.main import app
    from ingestion.models import (
        BondYieldSnapshot,
        Decision,
        PriceHistoryLong,
        Security,
        StrategicReport,
    )

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, autoflush=False, future=True)
        base = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=9)
        with engine.begin() as conn:
            conn.execute(
                Security.__table__.insert(),
                [
                    {"symbol": "AIR.PA", "name": "Airbus", "country": "FR", "currency": "EUR", "sector": "Industrie", "theme": "CAC 40"},
                    {"symbol": "MC.PA", "name": "LVMH", "country": "FR", "currency": "EUR", "sector": "Luxe", "theme": "CAC 40"},
                    {"symbol": "ALO.PA", "name": "Alstom", "country": "FR", "currency": "EUR", "sector": "Industrie", "theme": "CAC Mid 60"},
                ],
            )
            conn.execute(
                PriceHistoryLong.__table__.insert(),
                [
                    {"symbol": s, "ts": base + pd.Timedelta(days=i), "open": p, "high": p, "low": p, "close": p + i, "volume": 1000}
                    for s, p in (("AIR.PA", 200.0), ("MC.PA", 400.0), ("ALO.PA", 20.0))
                    for i in range(10)
                ],
            )
            conn.execute(
                Decision.__table__.insert(),
                [
                    {"symbol": "AIR.PA", "decision_type": "Achat", "status": "proposee", "entry_price": 209, "confidence": 80},
                    {"symbol": "MC.PA", "decision_type": "Surveiller", "status": "proposee", "entry_price": 409, "confidence": 60},
                    {"symbol": "ALO.PA", "decision_type": "Achat", "status": "proposee", "entry_price": 29, "confidence": 99},
                ],
            )
            conn.execute(
                BondYieldSnapshot.__table__.insert(),
                [
                    {"instrument": "OAT_FR_10Y", "value_pct": 4.9, "observed_at": datetime.date(2026, 9, 1), "source_name": "FRED"},
                    {"instrument": "BUND_DE_10Y", "value_pct": 3.5, "observed_at": datetime.date(2026, 9, 1), "source_name": "FRED"},
                ],
            )

        monkeypatch.setattr(strategic_report, "fetch_cac40_index", lambda: {"close": 7934.7, "as_of": "2026-10-15", "week_change_pct": 1.68, "source": "test"})
        monkeypatch.setattr(strategic_report, "fetch_web_sources", lambda: [{"n": 1, "theme": "CAC 40", "titre": "T", "url": "https://ex.com", "extrait": "x"}])
        captured = {}

        def fake_complete(system_prompt, user_message, **kwargs):
            captured["context"] = user_message
            return "## Synthèse exécutive\n\n- Test"

        monkeypatch.setattr(mistral_client, "complete", fake_complete)

        first_id = strategic_report.generate_report(session_factory)
        second_id = strategic_report.generate_report(session_factory)

        with session_factory() as db:
            first = db.get(StrategicReport, first_id)
            assert first.risk_level == "orange"  # OAT 4,9 % / spread 140 pb
            assert first.data["cac40_index"]["close"] == 7934.7
            assert [r["symbol"] for r in first.data["cac40"]] == ["AIR.PA", "MC.PA"]  # univers CAC 40 seulement
            assert "portfolio" not in first.data
            assert db.scalar(select(func.count()).select_from(StrategicReport)) == 2
        assert "Airbus" in captured["context"] and "ALO.PA" not in captured["context"]

        monkeypatch.setattr(deps, "engine", engine)
        monkeypatch.setattr(deps, "SessionLocal", session_factory)
        monkeypatch.setitem(app.dependency_overrides, auth.require_user, lambda: "test-user-id")
        client = TestClient(app)
        latest = client.get("/strategic-reports/latest").json()
        assert latest["id"] == second_id and latest["narrative_markdown"].startswith("## Synthèse")
        assert [r["id"] for r in client.get("/strategic-reports").json()] == [second_id, first_id]
        assert client.get("/strategic-reports/999999").status_code == 404
        engine.dispose()
    finally:
        command.downgrade(cfg, "base")


def test_non_finite_values_never_reach_calculations_or_jsonb():
    import types

    nan = float("nan")
    assert strategic_report._f(nan) is None and strategic_report._f(float("inf")) is None
    assert strategic_report._json_safe({"a": [1.0, nan], "b": {"c": float("-inf")}, "d": "x"}) == {
        "a": [1.0, None],
        "b": {"c": None},
        "d": "x",
    }
    rows = [("A", datetime.datetime(2026, 10, d), 10.0) for d in range(1, 15)] + [
        ("A", datetime.datetime(2026, 10, 15), nan)
    ]
    result = strategic_report._recent_closes(types.SimpleNamespace(execute=lambda stmt: rows), ["A"], datetime.date(2026, 10, 16))
    assert result["A"]["close"] == 10.0 and result["A"]["as_of"] == "2026-10-14"


def test_generation_job_uses_a_dedicated_unpooled_engine(monkeypatch):
    """Régression : en production, la génération échouait sur « QueuePool
    limit of size 2 overflow 2 reached » quand l'écran Univers occupait tout
    le pool de l'API. Le job passe désormais par son propre moteur sans pool,
    construit sur la même URL."""
    from sqlalchemy.pool import NullPool

    from api import deps
    from api.routers import strategic_reports

    seen = {}

    def fake_generate(session_factory, now=None):
        bind = session_factory.kw["bind"]
        seen["pool"] = type(bind.pool)
        seen["url"] = bind.url
        return 7

    monkeypatch.setattr(strategic_reports, "_state", {"status": "running"})
    monkeypatch.setattr(strategic_report, "generate_report", fake_generate)
    strategic_reports._run_generation_job()
    assert seen["pool"] is NullPool and seen["url"] == deps.engine.url
    assert strategic_reports._state["status"] == "done" and strategic_reports._state["report_id"] == 7
