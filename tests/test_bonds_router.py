"""Tests de `api/routers/bonds.py:update_bond_alert_threshold` -- DB réelle
(testcontainers, nécessite Docker). Couvre un bug trouvé par /code-review :
un PATCH qui change `threshold_pct` et désactive le seuil dans le même appel
doit écrire l'événement "resolved" avec l'ANCIEN seuil (celui réellement
franchi), pas le nouveau -- sinon le journal d'alertes (`BondAlertEvent`)
mentirait sur la valeur qui a déclenché l'alerte."""

import datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from api.routers.bonds import update_bond_alert_threshold
from api.schemas import BondAlertThresholdUpdateRequest
from engine.bond_alerts import evaluate_all_thresholds
from ingestion.models import BOND_INSTRUMENT_OAT_FR_10Y, BondAlertEvent, BondAlertThreshold, BondYieldSnapshot


def test_patch_disabling_and_changing_threshold_in_one_call_resolves_with_the_old_threshold(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)

        with session_factory() as db:
            threshold = BondAlertThreshold(
                instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True
            )
            db.add(threshold)
            db.commit()
            db.refresh(threshold)
            threshold_id = threshold.id

        with session_factory() as db:
            stmt = pg_insert(BondYieldSnapshot).values(
                instrument=BOND_INSTRUMENT_OAT_FR_10Y, value_pct=5.10, observed_at=datetime.date(2026, 10, 1), source_name="FRED"
            )
            db.execute(stmt)
            db.commit()
            created = evaluate_all_thresholds(db)
            # Lu pendant que la session est encore ouverte : evaluate_all_thresholds
            # commit en interne, ce qui expire les objets qu'elle renvoie (défaut
            # SQLAlchemy expire_on_commit) -- y accéder après la fermeture de `db`
            # (sortie du `with`) lève DetachedInstanceError.
            created_status = created[0].status if created else None
        assert len(created) == 1 and created_status == "triggered"

        # Un seul PATCH change le seuil ET désactive -- l'événement "resolved"
        # doit référencer 4.90 (le seuil réellement franchi), pas 5.50.
        with session_factory() as db:
            threshold = db.get(BondAlertThreshold, threshold_id)
            update_bond_alert_threshold(
                threshold_id, BondAlertThresholdUpdateRequest(threshold_pct=5.50, enabled=False), db
            )

        with session_factory() as db:
            events = db.execute(select(BondAlertEvent).order_by(BondAlertEvent.triggered_at)).scalars().all()
            threshold = db.get(BondAlertThreshold, threshold_id)
        assert [e.status for e in events] == ["triggered", "resolved"]
        assert float(events[-1].threshold_pct) == 4.90
        assert "4.9" in events[-1].message
        assert float(threshold.threshold_pct) == 5.50
        assert threshold.enabled is False
    finally:
        command.downgrade(cfg, "base")


def test_patch_changing_only_threshold_pct_does_not_touch_alert_events(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)

        with session_factory() as db:
            threshold = BondAlertThreshold(
                instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True
            )
            db.add(threshold)
            db.commit()
            db.refresh(threshold)
            threshold_id = threshold.id

        with session_factory() as db:
            threshold = db.get(BondAlertThreshold, threshold_id)
            update_bond_alert_threshold(threshold_id, BondAlertThresholdUpdateRequest(threshold_pct=5.00), db)

        with session_factory() as db:
            events = db.execute(select(BondAlertEvent)).scalars().all()
            threshold = db.get(BondAlertThreshold, threshold_id)
        assert events == []
        assert float(threshold.threshold_pct) == 5.00
        assert threshold.enabled is True
    finally:
        command.downgrade(cfg, "base")


def test_patch_unknown_threshold_id_raises_404(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            with pytest.raises(Exception) as exc_info:
                update_bond_alert_threshold(999999, BondAlertThresholdUpdateRequest(enabled=False), db)
            assert "404" in str(exc_info.value) or "inconnu" in str(exc_info.value)
    finally:
        command.downgrade(cfg, "base")
