from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select

from ingestion.cac40 import CAC40_SECURITIES
from ingestion.cac_mid60 import CAC_MID60_SECURITIES
from ingestion.models import Security
from ingestion.seed import seed_securities

TOTAL_UNIVERSE_SIZE = len(CAC40_SECURITIES) + len(CAC_MID60_SECURITIES)


def test_no_duplicate_symbols_between_cac40_and_cac_mid60():
    cac40_symbols = {s for s, *_ in CAC40_SECURITIES}
    mid60_symbols = {s for s, *_ in CAC_MID60_SECURITIES}
    assert cac40_symbols.isdisjoint(mid60_symbols)


def test_seed_loads_cac40_and_mid60_universe_idempotently(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        inserted = seed_securities()
        assert inserted == TOTAL_UNIVERSE_SIZE

        engine = create_engine(database_url, future=True)
        with engine.connect() as conn:
            rows = conn.execute(select(Security)).fetchall()
        assert len(rows) == TOTAL_UNIVERSE_SIZE
        assert {r.theme for r in rows} == {"CAC 40", "CAC Mid 60"}

        # Ré-exécuter le seed est sans danger (upsert) : pas de doublons.
        seed_securities()
        with engine.connect() as conn:
            rows_after = conn.execute(select(Security)).fetchall()
        assert len(rows_after) == TOTAL_UNIVERSE_SIZE
    finally:
        command.downgrade(cfg, "base")
