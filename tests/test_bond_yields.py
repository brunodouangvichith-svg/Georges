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

    monkeypatch.setattr(bond_yields.requests, "get", lambda url, **kwargs: _FakeResponse(FRED_CSV_DAILY))
    result = fetch_bond_yield("DGS10")
    assert result is not None
    value_pct, observed_at = result
    assert value_pct == 4.15
    assert observed_at == datetime.date(2026, 10, 13)


def test_fetch_bond_yield_skips_a_missing_latest_observation(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(
        bond_yields.requests, "get", lambda url, **kwargs: _FakeResponse(FRED_CSV_WITH_MISSING_LATEST)
    )
    result = fetch_bond_yield("DGS2")
    assert result is not None
    value_pct, observed_at = result
    assert value_pct == 3.90
    assert observed_at == datetime.date(2026, 10, 12)


def test_fetch_bond_yield_returns_none_when_every_observation_is_missing(monkeypatch):
    import ingestion.bond_yields as bond_yields

    monkeypatch.setattr(
        bond_yields.requests, "get", lambda url, **kwargs: _FakeResponse(FRED_CSV_ALL_MISSING)
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


def _fred_csv_for(params, *dates_values):
    series_id = (params or {}).get("id", "X")
    rows = "".join(f"{d.isoformat()},{v}\n" for d, v in dates_values)
    return f"observation_date,{series_id}\n{rows}"


def test_run_is_idempotent_and_logs_the_collection_run(database_url, monkeypatch):
    """Sans clé Webstat et Bundesbank vide : OAT/Bund passent par le repli
    FRED mensuel ; relancer ne crée aucun doublon."""
    import ingestion.bond_yields as bond_yields

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        today = datetime.date.today()
        monkeypatch.delenv("WEBSTAT_API_KEY", raising=False)

        def fake_get(url, params=None, **kwargs):
            if "fred" in url:
                return _FakeResponse(
                    _fred_csv_for(params, (today - datetime.timedelta(days=2), 4.12), (today - datetime.timedelta(days=1), 4.15))
                )
            return _FakeResponse("")  # Bundesbank sans données -> repli

        monkeypatch.setattr(bond_yields.requests, "get", fake_get)
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
            assert count == 1  # repli = dernière valeur seulement, jamais de doublon
            runs = db.execute(select(BondCollectionRun).order_by(BondCollectionRun.started_at)).scalars().all()
            assert len(runs) == 2
            assert all(r.status == "success" for r in runs)
            assert all(r.instruments_succeeded == 4 for r in runs)
            assert all("repli" in (r.error_summary or "") for r in runs)
        engine.dispose()
    finally:
        command.downgrade(cfg, "base")


def test_daily_source_replaces_monthly_rows_and_fallback_never_overwrites(database_url, monkeypatch):
    """Bundesbank (quotidien) remplace, sur sa fenêtre, la moyenne mensuelle
    FRED ; un jour où elle est en panne, le repli FRED n'écrase pas la valeur
    quotidienne de même date."""
    import ingestion.bond_yields as bond_yields

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        today = datetime.date.today()
        d0, d1, d2 = (today - datetime.timedelta(days=n) for n in (3, 2, 1))
        engine = create_engine(database_url, future=True)
        with engine.begin() as conn:
            conn.execute(
                BondYieldSnapshot.__table__.insert(),
                [{"instrument": "BUND_DE_10Y", "value_pct": 2.90, "observed_at": d1, "source_name": "FRED (OCDE, mensuel)", "source_url": "x"}],
            )
        monkeypatch.delenv("WEBSTAT_API_KEY", raising=False)
        bundesbank_up = {"ok": True}

        def fake_get(url, params=None, **kwargs):
            if "bundesbank" in url:
                if not bundesbank_up["ok"]:
                    raise bond_yields.requests.ConnectionError("panne")
                return _FakeResponse(f"Stand;x;\n{d0.isoformat()};3,51;\n{d1.isoformat()};3,45;\n{d2.isoformat()};3,48;\n")
            return _FakeResponse(_fred_csv_for(params, (d2, 2.75)))

        monkeypatch.setattr(bond_yields.requests, "get", fake_get)
        bond_yields.run()
        with sessionmaker(bind=engine, future=True)() as db:
            rows = (
                db.execute(
                    select(BondYieldSnapshot)
                    .where(BondYieldSnapshot.instrument == "BUND_DE_10Y")
                    .order_by(BondYieldSnapshot.observed_at)
                )
                .scalars()
                .all()
            )
            assert [(r.observed_at, float(r.value_pct), r.source_name) for r in rows] == [
                (d0, 3.51, "Bundesbank"),
                (d1, 3.45, "Bundesbank"),
                (d2, 3.48, "Bundesbank"),
            ]

        bundesbank_up["ok"] = False
        bond_yields.run()
        with sessionmaker(bind=engine, future=True)() as db:
            latest = db.execute(
                select(BondYieldSnapshot).where(BondYieldSnapshot.instrument == "BUND_DE_10Y", BondYieldSnapshot.observed_at == d2)
            ).scalar_one()
            assert float(latest.value_pct) == 3.48 and latest.source_name == "Bundesbank"
        engine.dispose()
    finally:
        command.downgrade(cfg, "base")


def test_parse_bundesbank_csv_reads_decimal_commas_and_skips_headers():
    from ingestion.bond_yields import parse_bundesbank_csv

    text = "Kommentar (englisch);;\nStand vom;16.10.2026 12:13:05 Uhr;\n2026-10-15;3,45;\n2026-10-14;3,51;\n2026-10-13;.;\n"
    assert parse_bundesbank_csv(text) == [(3.51, datetime.date(2026, 10, 14)), (3.45, datetime.date(2026, 10, 15))]


def test_parse_webstat_records_skips_days_without_quote_and_sorts():
    from ingestion.bond_yields import parse_webstat_records

    payload = {
        "total_count": 3,
        "results": [
            {"time_period": "2026-10-10", "obs_value": None},
            {"time_period": "2026-10-16", "obs_value": 3.62},
            {"time_period": "2026-10-15", "obs_value": 3.58},
        ],
    }
    assert parse_webstat_records(payload) == [(3.58, datetime.date(2026, 10, 15)), (3.62, datetime.date(2026, 10, 16))]
    assert parse_webstat_records([{"time_period": "2026-10-16", "obs_value": "3.6"}]) == [(3.6, datetime.date(2026, 10, 16))]


def test_fetch_webstat_history_needs_the_key_and_sends_it_as_apikey_header(monkeypatch):
    import ingestion.bond_yields as bond_yields

    calls = []

    class _Json(_FakeResponse):
        def json(self):
            return {"results": [{"time_period": datetime.date.today().isoformat(), "obs_value": 3.6}]}

    def fake_get(url, params=None, headers=None, **kwargs):
        calls.append((url, params, headers))
        return _Json("")

    monkeypatch.setattr(bond_yields.requests, "get", fake_get)
    monkeypatch.delenv("WEBSTAT_API_KEY", raising=False)
    assert bond_yields.fetch_webstat_history("S", datetime.date.today() - datetime.timedelta(days=5)) is None
    assert calls == []

    monkeypatch.setenv("WEBSTAT_API_KEY", " secret ")
    history = bond_yields.fetch_webstat_history("S", datetime.date.today() - datetime.timedelta(days=5))
    assert history == [(3.6, datetime.date.today())]
    url, params, headers = calls[0]
    assert url.endswith("/observations/records") and headers == {"Authorization": "Apikey secret"}
    assert params["where"] == 'series_key="S"' and params["order_by"] == "time_period desc"
    # Historique long : export complet plutôt que la pagination de /records.
    bond_yields.fetch_webstat_history("S", datetime.date(2016, 1, 1))
    assert calls[1][0].endswith("/observations/exports/json")


def test_oat_and_bund_try_daily_sources_first():
    from ingestion.bond_yields import BOND_YIELD_SERIES

    sources = dict(BOND_YIELD_SERIES)
    assert [s.name for s in sources["OAT_FR_10Y"]] == ["Banque de France (TEC10)", "FRED (OCDE, mensuel)"]
    assert [s.name for s in sources["BUND_DE_10Y"]] == ["Bundesbank", "FRED (OCDE, mensuel)"]
    assert all("apikey" not in s.url.lower() for pairs in sources.values() for s in pairs)


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

    monkeypatch.setattr(bond_yields.requests, "get", lambda url, **kwargs: _FakeResponse(FRED_CSV_HISTORY))
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

    def _fake_collect(instrument, sources, since):
        if instrument == "UST_US_2Y":
            return None  # aucune source joignable : les autres continuent
        return sources[0], [(4.0, since), (4.1, since + datetime.timedelta(days=1))]

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext("conn")

    written_calls = []
    monkeypatch.setattr(bond_yields, "_collect", _fake_collect)
    monkeypatch.setattr(bond_yields, "get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(bond_yields, "_write", lambda conn, instrument, source, obs: written_calls.append((instrument, len(obs))))

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
    bond_yields._upsert_snapshots(_FakeConn(), "UST_US_10Y", bond_yields.BUNDESBANK_BUND10, observations)
    assert len(executed) == 3  # 2 + 2 + 1
