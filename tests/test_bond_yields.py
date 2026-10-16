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


# --- Rattrapage de l'historique (`backfill_history`) -- pur, réseau et DB mockés ---

FRED_CSV_HISTORY = (
    "observation_date,DGS10\n"
    "2014-01-02,3.00\n"
    "2025-01-02,4.50\n"
    "2025-01-03,.\n"
    "2026-10-13,4.15\n"
    "pas-une-date,4.20\n"
)


def test_parse_fred_csv_keeps_real_values_in_order_and_skips_missing_or_malformed():
    from ingestion.bond_yields import parse_fred_csv

    assert parse_fred_csv(FRED_CSV_HISTORY, "DGS10") == [
        (3.00, datetime.date(2014, 1, 2)),
        (4.50, datetime.date(2025, 1, 2)),
        (4.15, datetime.date(2026, 10, 13)),
    ]
    # Colonne absente (mauvais ID de série) -> rien, jamais une valeur inventée.
    assert parse_fred_csv(FRED_CSV_HISTORY, "DGS2") == []


def test_fetch_bond_yield_history_filters_by_start_date(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(bond_yields.requests, "get", lambda url, params=None, timeout=None: _FakeResponse(FRED_CSV_HISTORY))
    history = bond_yields.fetch_bond_yield_history("DGS10", since=datetime.date(2025, 1, 1))
    assert history == [(4.50, datetime.date(2025, 1, 2)), (4.15, datetime.date(2026, 10, 13))]


def test_fetch_bond_yield_history_returns_none_on_network_failure(monkeypatch):
    import ingestion.bond_yields as bond_yields

    def _raise(*_args, **_kwargs):
        raise bond_yields.requests.ConnectionError("réseau coupé")

    monkeypatch.setattr(bond_yields.requests, "get", _raise)
    assert bond_yields.fetch_bond_yield_history("DGS10", since=datetime.date(2020, 1, 1)) is None


def test_backfill_history_upserts_each_series_and_reports_unreachable_ones(monkeypatch):
    import contextlib

    import ingestion.bond_yields as bond_yields

    def _fake_history(series_id, since):
        if series_id == "DGS2":
            return None  # série injoignable : les autres doivent continuer
        return [(4.0, since), (4.1, since + datetime.timedelta(days=1))]

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext("conn")

    written_calls = []
    monkeypatch.setattr(bond_yields, "fetch_bond_yield_history", _fake_history)
    monkeypatch.setattr(bond_yields, "get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        bond_yields, "_upsert_snapshots", lambda conn, instrument, series_id, obs: written_calls.append((instrument, len(obs)))
    )

    result = bond_yields.backfill_history(years=2)

    assert result == {"OAT_FR_10Y": 2, "BUND_DE_10Y": 2, "UST_US_10Y": 2, "UST_US_2Y": None}
    assert written_calls == [("OAT_FR_10Y", 2), ("BUND_DE_10Y", 2), ("UST_US_10Y", 2)]


def test_upsert_snapshots_splits_large_histories_into_batches(monkeypatch):
    import ingestion.bond_yields as bond_yields

    executed = []

    class _FakeConn:
        def execute(self, stmt):
            executed.append(stmt)

    monkeypatch.setattr(bond_yields, "UPSERT_BATCH_SIZE", 2)
    observations = [(4.0 + i / 100, datetime.date(2026, 1, 1) + datetime.timedelta(days=i)) for i in range(5)]
    bond_yields._upsert_snapshots(_FakeConn(), "UST_US_10Y", "DGS10", observations)
    assert len(executed) == 3  # 2 + 2 + 1
