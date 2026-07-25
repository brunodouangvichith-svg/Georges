from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select

from ingestion.cac40 import CAC40_SECURITIES
from ingestion.models import Security
from ingestion.seed import seed_securities


def test_seed_loads_cac40_universe_idempotently(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        inserted = seed_securities()
        assert inserted == len(CAC40_SECURITIES)

        engine = create_engine(database_url, future=True)
        with engine.connect() as conn:
            rows = conn.execute(select(Security)).fetchall()
        assert len(rows) == len(CAC40_SECURITIES)

        # Ré-exécuter le seed est sans danger (upsert) : pas de doublons.
        seed_securities()
        with engine.connect() as conn:
            rows_after = conn.execute(select(Security)).fetchall()
        assert len(rows_after) == len(CAC40_SECURITIES)
    finally:
        command.downgrade(cfg, "base")
