"""Tests de `agents/macro_context.py`. Nécessite un vrai Postgres
(testcontainers, fixture `database_url` — nécessite Docker, comme
`tests/test_jane_knowledge.py`)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.macro_context import get_latest_macro_snapshots
from ingestion.models import MacroIndicatorSnapshot


def test_get_latest_macro_snapshots_keeps_one_row_per_indicator_and_source(database_url):
    """EUR/USD suivi par deux sources indépendantes (FRED, BCE) : les deux
    doivent ressortir, jamais fusionnées/moyennées (voir docstring du
    module — le recoupement multi-source doit rester visible)."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            db.add_all(
                [
                    MacroIndicatorSnapshot(
                        indicator="Taux de change EUR/USD",
                        value=1.1385,
                        unit=None,
                        source_name="FRED",
                        observed_at="2026-09-15",
                        reliability_score=0.9,
                    ),
                    MacroIndicatorSnapshot(
                        indicator="Taux de change EUR/USD",
                        value=1.1389,
                        unit=None,
                        source_name="BCE",
                        observed_at="2026-09-15",
                        reliability_score=0.9,
                    ),
                    MacroIndicatorSnapshot(
                        indicator="Taux OAT 10 ans (France)",
                        value=3.68,
                        unit="%",
                        source_name="FRED",
                        observed_at="2026-09-12",
                        reliability_score=0.6,
                    ),
                ]
            )
            db.commit()

            snapshots = get_latest_macro_snapshots(db)

            by_source = {(s["indicateur"], s["source"]): s for s in snapshots}
            assert by_source[("Taux de change EUR/USD", "FRED")]["valeur"] == 1.1385
            assert by_source[("Taux de change EUR/USD", "BCE")]["valeur"] == 1.1389
            assert by_source[("Taux OAT 10 ans (France)", "FRED")]["valeur"] == 3.68
            assert by_source[("Taux OAT 10 ans (France)", "FRED")]["unite"] == "%"
    finally:
        command.downgrade(cfg, "base")


def test_get_latest_macro_snapshots_keeps_only_the_most_recent_row_per_source(database_url):
    """Deux instantanés successifs de la même (indicateur, source) — dû à
    deux cycles de collecte différents (`observed_at` différent) — ne
    doivent laisser que le plus récemment inséré (`created_at`), pas les
    deux ni le plus ancien."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            db.add(
                MacroIndicatorSnapshot(
                    indicator="Taux OAT 10 ans (France)",
                    value=3.60,
                    unit="%",
                    source_name="FRED",
                    observed_at="2026-08-01",
                    reliability_score=0.6,
                )
            )
            db.commit()
            db.add(
                MacroIndicatorSnapshot(
                    indicator="Taux OAT 10 ans (France)",
                    value=3.68,
                    unit="%",
                    source_name="FRED",
                    observed_at="2026-09-12",
                    reliability_score=0.6,
                )
            )
            db.commit()

            snapshots = get_latest_macro_snapshots(db)
            matching = [s for s in snapshots if s["indicateur"] == "Taux OAT 10 ans (France)" and s["source"] == "FRED"]
            assert len(matching) == 1
            assert matching[0]["valeur"] == 3.68


        engine.dispose()
    finally:
        command.downgrade(cfg, "base")


def test_get_latest_macro_snapshots_does_not_drop_a_low_frequency_indicator(database_url):
    """Régression `/code-review` : un indicateur mensuel (ex. Eurostat
    chômage/inflation, une seule ligne jamais réécrite car
    `on_conflict_do_update` ne touche jamais `created_at`) ne doit jamais
    disparaître au profit d'un indicateur à cadence rapide (FRED/BCE/
    Frankfurter, un nouveau `observed_at`/une nouvelle ligne à chaque
    cycle) même quand ce dernier accumule beaucoup plus de lignes au fil
    du temps."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            db.add(
                MacroIndicatorSnapshot(
                    indicator="Taux de chômage (zone euro)",
                    value=6.3,
                    unit="%",
                    source_name="Eurostat",
                    observed_at="2026-07",
                    reliability_score=0.6,
                )
            )
            db.commit()

            # Simule de nombreux cycles ultérieurs d'un indicateur à cadence
            # rapide, largement au-delà de l'ancienne limite de fenêtre
            # (RECENT_ROWS_LIMIT = 50) qui aurait fait disparaître la ligne
            # Eurostat ci-dessus.
            for i in range(60):
                db.add(
                    MacroIndicatorSnapshot(
                        indicator="Taux de change EUR/USD",
                        value=1.10 + i * 0.0001,
                        unit=None,
                        source_name="FRED",
                        observed_at=f"2026-09-{(i % 28) + 1:02d}-cycle{i}",
                        reliability_score=0.9,
                    )
                )
                db.commit()

            snapshots = get_latest_macro_snapshots(db)
            matching = [
                s for s in snapshots if s["indicateur"] == "Taux de chômage (zone euro)" and s["source"] == "Eurostat"
            ]
            assert len(matching) == 1
            assert matching[0]["valeur"] == 6.3
    finally:
        command.downgrade(cfg, "base")


def test_get_latest_macro_snapshots_returns_empty_list_when_never_collected(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            assert get_latest_macro_snapshots(db) == []
    finally:
        command.downgrade(cfg, "base")
