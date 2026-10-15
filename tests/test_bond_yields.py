"""Tests de `ingestion/bond_yields.py` -- réseau mocké pour `fetch_bond_yield`
(même principe que `tests/test_collectors.py` pour `agents/collectors/macro.py`,
dont le CSV FRED est au même format). `run()` écrit en DB réelle
(testcontainers, nécessite Docker) -- vérifie l'upsert idempotent demandé
par le cahier des charges §6 ("éviter les doublons")."""

import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from ingestion.bond_yields import BOND_YIELD_SERIES, fetch_bond_yield
from ingestion.models import BOND_INSTRUMENT_OAT_FR_10Y, BondCollectionRun, BondYieldSnapshot

FRED_CSV_DAILY = "observation_date,DGS10\n2026-10-12,4.12\n2026-10-13,4.15\n"
FRED_CSV_WITH_MISSING_LATEST = "observation_date,DGS2\n2026-10-12,3.90\n2026-10-13,.\n"
FRED_CSV_ALL_MISSING = "observation_date,DGS10\n2026-10-12,.\n2026-10-13,.\n"


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_bond_yield_returns_the_latest_real_value(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(bond_yields.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV_DAILY))
    result = fetch_bond_yield("DGS10")
    assert result is not None
    value_pct, observed_at = result
    assert value_pct == 4.15
    assert observed_at == datetime.date(2026, 10, 13)


def test_fetch_bond_yield_skips_a_missing_latest_observation(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(
        bond_yields.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV_WITH_MISSING_LATEST)
    )
    result = fetch_bond_yield("DGS2")
    assert result is not None
    value_pct, observed_at = result
    assert value_pct == 3.90
    assert observed_at == datetime.date(2026, 10, 12)


def test_fetch_bond_yield_returns_none_when_every_observation_is_missing(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(
        bond_yields.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV_ALL_MISSING)
    )
    assert fetch_bond_yield("DGS10") is None


def test_fetch_bond_yield_returns_none_on_network_failure(monkeypatch):
    import ingestion.bond_yields as bond_yields
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(bond_yields.requests, "get", _raise)
    assert fetch_bond_yield("DGS10") is None


def test_bond_yield_series_covers_the_four_tracked_instruments():
    instruments = {instrument for instrument, _series_id in BOND_YIELD_SERIES}
    assert instruments == {"OAT_FR_10Y", "BUND_DE_10Y", "UST_US_10Y", "UST_US_2Y"}


def test_run_is_idempotent_and_logs_the_collection_run(database_url, monkeypatch):
    import ingestion.bond_yields as bond_yields

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(
            bond_yields.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV_DAILY)
        )
        # `FRED_CSV_DAILY` sert les 4 séries ici (même CSV, même point final) --
        # seul l'upsert/l'idempotence compte dans ce test, pas la valeur exacte par instrument.
        summary_first = bond_yields.run()
        assert all(summary_first.values())

        summary_second = bond_yields.run()
        assert all(summary_second.values())

        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            count = db.scalar(
                select(func.count()).select_from(BondYieldSnapshot).where(BondYieldSnapshot.instrument == BOND_INSTRUMENT_OAT_FR_10Y)
            )
            assert count == 1  # même (instrument, observed_at) relancé deux fois -> une seule ligne, pas un doublon

            runs = db.execute(select(BondCollectionRun).order_by(BondCollectionRun.started_at)).scalars().all()
            assert len(runs) == 2
            assert all(r.status == "success" for r in runs)
            assert all(r.instruments_succeeded == 4 for r in runs)
    finally:
        command.downgrade(cfg, "base")
