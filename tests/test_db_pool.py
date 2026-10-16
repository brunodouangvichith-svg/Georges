"""Configuration du pool SQLAlchemy (`ingestion/db.py:get_engine`).

Pur : `create_engine` n'ouvre aucune connexion tant qu'on ne s'en sert pas,
donc ni Docker ni base ne sont nécessaires.
"""

import pytest

from ingestion import db

URL = "postgresql+psycopg://u:p@127.0.0.1:5432/x"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)


def test_default_pool_is_small():
    engine = db.get_engine()
    pool = engine.pool
    assert pool.size() == db.DEFAULT_POOL_SIZE == 2
    assert pool._max_overflow == db.DEFAULT_MAX_OVERFLOW == 2
    assert pool._timeout == db.POOL_TIMEOUT_SECONDS
    assert pool._recycle == db.POOL_RECYCLE_SECONDS
    assert pool._pre_ping is True
    engine.dispose()


def test_pool_overridable_by_env(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    engine = db.get_engine()
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 0
    engine.dispose()


@pytest.mark.parametrize("raw", ["", "  ", "abc", "0", "-3"])
def test_invalid_pool_size_falls_back_to_default(monkeypatch, raw):
    monkeypatch.setenv("DB_POOL_SIZE", raw)
    engine = db.get_engine()
    assert engine.pool.size() == db.DEFAULT_POOL_SIZE
    engine.dispose()


def test_negative_overflow_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("DB_MAX_OVERFLOW", "-1")
    engine = db.get_engine()
    assert engine.pool._max_overflow == db.DEFAULT_MAX_OVERFLOW
    engine.dispose()
