"""Vérifie que les migrations Alembic s'appliquent proprement sur une base vide.

Nécessite un démon Docker local (testcontainers lance une instance Postgres
jetable) — voir `postgres_container` / `database_url` dans conftest.py.
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "securities",
    "prices_ohlcv",
    "price_history_long",
    "patterns_detected",
    "decisions",
    "decision_outcomes",
    "baskets",
    "basket_securities",
    "pattern_candidates",
    "agent_events",
    "strategic_reports",
    "virtual_portfolio_trades",
    "virtual_portfolio_snapshots",
}


def _alembic_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def test_migrations_apply_cleanly_on_empty_database(database_url):
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        tables = set(inspect(engine).get_table_names())
        assert EXPECTED_TABLES <= tables
    finally:
        command.downgrade(cfg, "base")


def test_migrations_downgrade_removes_all_tables(database_url):
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(database_url, future=True)
    tables = set(inspect(engine).get_table_names())
    assert not (EXPECTED_TABLES & tables)
