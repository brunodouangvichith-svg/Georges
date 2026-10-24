"""Tests de `engine/bond_alerts.py`. `_is_crossed`/`_format_message`/`_unit`
sont purs (aucune DB) ; `evaluate_all_thresholds` écrit en DB réelle
(testcontainers, nécessite Docker) -- vérifie la consigne explicite du
cahier des charges : "prévention des alertes répétitives inutiles" (un
seuil resté franchi ne doit produire qu'un seul événement, pas un par
cycle)."""

import datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from engine.bond_alerts import _format_message, _is_crossed, _unit, evaluate_all_thresholds, resolve_if_triggered
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS,
    BondAlertEvent,
    BondAlertThreshold,
    BondYieldSnapshot,
)


def test_is_crossed_above():
    assert _is_crossed("above", 5.0, 4.90) is True
    assert _is_crossed("above", 4.50, 4.90) is False


def test_is_crossed_below():
    assert _is_crossed("below", 1.0, 2.0) is True
    assert _is_crossed("below", 3.0, 2.0) is False


def test_is_crossed_rejects_unknown_direction():
    with pytest.raises(ValueError):
        _is_crossed("sideways", 5.0, 4.90)


def test_unit_is_basis_points_for_spread_and_percent_otherwise():
    assert _unit(BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS) == "pb"
    assert _unit(BOND_INSTRUMENT_OAT_FR_10Y) == "%"


def test_format_message_triggered_above():
    msg = _format_message(BOND_INSTRUMENT_OAT_FR_10Y, "above", 5.10, 4.90, resolved=False)
    assert "OAT_FR_10Y" in msg
    assert "4.9%" in msg or "4.90%" in msg or "4.9" in msg
    assert "dépassé" in msg


def test_format_message_resolved_above():
    msg = _format_message(BOND_INSTRUMENT_OAT_FR_10Y, "above", 4.80, 4.90, resolved=True)
    assert "repassé" in msg
    assert "sous" in msg


def test_format_message_uses_basis_points_unit_for_spread():
    msg = _format_message(BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS, "above", 160, 150, resolved=False)
    assert "pb" in msg
    assert "%" not in msg


def test_evaluate_all_thresholds_fires_once_then_resolves_then_refires(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)

        def _set_oat(value_pct, observed_at):
            with session_factory() as db:
                stmt = pg_insert(BondYieldSnapshot).values(
                    instrument=BOND_INSTRUMENT_OAT_FR_10Y,
                    value_pct=value_pct,
                    observed_at=observed_at,
                    source_name="FRED",
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[BondYieldSnapshot.instrument, BondYieldSnapshot.observed_at],
                    set_={"value_pct": stmt.excluded.value_pct},
                )
                db.execute(stmt)
                db.commit()

        with session_factory() as db:
            db.add(BondAlertThreshold(instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True))
            db.commit()

        _set_oat(5.10, datetime.date(2026, 10, 1))  # dépasse 4.90 -> doit déclencher
        with session_factory() as db:
            created = evaluate_all_thresholds(db)
        assert len(created) == 1
        assert created[0].status == "triggered"

        # Cycle suivant, toujours au-dessus du seuil -- ne doit RIEN recréer (anti-répétition).
        _set_oat(5.15, datetime.date(2026, 10, 2))
        with session_factory() as db:
            created_again = evaluate_all_thresholds(db)
        assert created_again == []

        # Repasse sous le seuil -- doit créer un événement "resolved".
        _set_oat(4.50, datetime.date(2026, 10, 3))
        with session_factory() as db:
            resolved = evaluate_all_thresholds(db)
        assert len(resolved) == 1
        assert resolved[0].status == "resolved"

        # Repasse au-dessus -- doit redéclencher un nouveau "triggered".
        _set_oat(5.20, datetime.date(2026, 10, 4))
        with session_factory() as db:
            retriggered = evaluate_all_thresholds(db)
        assert len(retriggered) == 1
        assert retriggered[0].status == "triggered"

        with session_factory() as db:
            all_events = db.execute(select(BondAlertEvent).order_by(BondAlertEvent.triggered_at)).scalars().all()
        assert [e.status for e in all_events] == ["triggered", "resolved", "triggered"]
    finally:
        command.downgrade(cfg, "base")


def test_evaluate_all_thresholds_ignores_missing_data(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            db.add(BondAlertThreshold(instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True))
            db.commit()
            # Aucun BondYieldSnapshot pour OAT_FR_10Y -- ne doit jamais fabriquer une alerte.
            created = evaluate_all_thresholds(db)
        assert created == []
    finally:
        command.downgrade(cfg, "base")


def test_evaluate_all_thresholds_does_not_fire_spread_alert_on_non_contemporaneous_observations(database_url):
    """Trouvé par /code-review : `latest_value_by_instrument` calculait le
    spread OAT-Bund à partir des dernières lignes de chaque instrument sans
    vérifier qu'elles sont contemporaines -- si le collecteur Bund tombe en
    panne pendant que l'OAT continue d'être collecté, un spread calculé
    entre un OAT frais et un Bund vieux de plusieurs mois pouvait franchir
    le seuil et déclencher une fausse alerte. Même discipline que
    `engine/compute_bond_yields.py:_values_if_contemporaneous` désormais
    réutilisée ici."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)

        def _set_snapshot(instrument, value_pct, observed_at):
            with session_factory() as db:
                stmt = pg_insert(BondYieldSnapshot).values(
                    instrument=instrument, value_pct=value_pct, observed_at=observed_at, source_name="FRED"
                )
                db.execute(stmt)
                db.commit()

        # OAT très frais, Bund vieux de 6 mois -- jamais contemporains
        # (tolérance de 45 jours). Naïvement, 4.00 - 1.00 = 300pb, bien
        # au-dessus du seuil de 150pb.
        _set_snapshot(BOND_INSTRUMENT_OAT_FR_10Y, 4.00, datetime.date(2026, 10, 1))
        _set_snapshot(BOND_INSTRUMENT_BUND_DE_10Y, 1.00, datetime.date(2026, 4, 1))

        with session_factory() as db:
            db.add(
                BondAlertThreshold(
                    instrument=BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS, direction="above", threshold_pct=150.0, enabled=True
                )
            )
            db.commit()
            created = evaluate_all_thresholds(db)
        assert created == []
    finally:
        command.downgrade(cfg, "base")


def test_resolve_if_triggered_writes_a_resolved_event_when_disabling_an_active_alert(database_url):
    """Désactiver un seuil actuellement "triggered" doit écrire un
    "resolved" explicite -- sinon `evaluate_all_thresholds` (qui ignore les
    seuils désactivés) ne le ferait jamais, et l'alerte resterait affichée
    comme active indéfiniment (bug trouvé par /code-review, voir le
    docstring de `resolve_if_triggered`)."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)

        with session_factory() as db:
            threshold = BondAlertThreshold(instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True)
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
        assert len(created) == 1 and created[0].status == "triggered"

        # Désactivation -- doit écrire un "resolved" explicite tout de suite,
        # pas seulement omettre le seuil du prochain evaluate_all_thresholds.
        with session_factory() as db:
            threshold = db.get(BondAlertThreshold, threshold_id)
            event = resolve_if_triggered(db, threshold)
            db.commit()
        assert event is not None
        assert event.status == "resolved"
        assert "désactivée" in event.message

        with session_factory() as db:
            events = db.execute(select(BondAlertEvent).order_by(BondAlertEvent.triggered_at)).scalars().all()
        assert [e.status for e in events] == ["triggered", "resolved"]
    finally:
        command.downgrade(cfg, "base")


def test_resolve_if_triggered_is_a_no_op_when_nothing_is_currently_triggered(database_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            threshold = BondAlertThreshold(instrument=BOND_INSTRUMENT_OAT_FR_10Y, direction="above", threshold_pct=4.90, enabled=True)
            db.add(threshold)
            db.commit()
            event = resolve_if_triggered(db, threshold)
        assert event is None
    finally:
        command.downgrade(cfg, "base")
