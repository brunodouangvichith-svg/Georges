"""Détection de franchissement de seuil pour Obligataire Watch (ad hoc, pas
une phase du roadmap). Contrairement à `engine/bond_spread.py`, ce module
touche la DB directement (même tier que `engine/monitor_decisions.py`) :
lire les seuils configurés, comparer à la dernière valeur connue, et
n'écrire un nouvel événement que lors d'un changement d'état réel.

**Anti-répétition par transition, pas par valeur** (demandé explicitement
par le cahier des charges) : un seuil resté franchi pendant 30 jours
consécutifs ne produit qu'un seul `BondAlertEvent` ("triggered"), pas un par
jour — un second événement n'est écrit que si le statut change réellement
("resolved" au retour sous le seuil, puis un nouveau "triggered" si le seuil
est de nouveau franchi plus tard). Les événements ne sont jamais modifiés
après écriture, seulement ajoutés — même discipline "append-only" que
`AgentEvent`/`JaneSecondOpinion` ailleurs dans ce projet.

Une valeur manquante pour un instrument ne déclenche jamais d'alerte
(silencieusement ignoré) plutôt que de fabriquer un franchissement sur une
donnée absente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.bond_spread import spread_bps
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS,
    BondAlertEvent,
    BondAlertThreshold,
    BondYieldSnapshot,
)

# Unité d'affichage par instrument, pour des messages d'alerte lisibles —
# tous en pourcentage sauf le spread (points de base), voir le docstring de
# `ingestion.models.BondAlertThreshold` pour pourquoi cette colonne mélange
# les deux unités selon l'instrument.
_UNIT_SUFFIX = {BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS: "pb"}


def _unit(instrument: str) -> str:
    return _UNIT_SUFFIX.get(instrument, "%")


def latest_value_by_instrument(db: Session) -> dict[str, float]:
    """Dernière valeur connue par instrument, à partir de la ligne la plus
    récente de `bond_yield_snapshots` pour chaque instrument réellement
    collecté, plus `BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS` calculé à la volée
    (jamais stocké lui-même — ce n'est pas une valeur observée chez une
    source externe). Un instrument jamais collecté est simplement absent du
    dict renvoyé ; le spread est absent si OAT ou Bund manque."""
    stmt = select(BondYieldSnapshot).order_by(BondYieldSnapshot.instrument, BondYieldSnapshot.observed_at.desc())
    latest: dict[str, float] = {}
    for row in db.execute(stmt).scalars():
        if row.instrument not in latest:
            latest[row.instrument] = float(row.value_pct)

    spread = spread_bps(latest.get(BOND_INSTRUMENT_OAT_FR_10Y), latest.get(BOND_INSTRUMENT_BUND_DE_10Y))
    if spread is not None:
        latest[BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS] = spread
    return latest


def _is_crossed(direction: str, value: float, threshold: float) -> bool:
    if direction == "above":
        return value > threshold
    if direction == "below":
        return value < threshold
    raise ValueError(f"direction de seuil inconnue : {direction!r} (attendu 'above' ou 'below')")


def _format_message(instrument: str, direction: str, value: float, threshold: float, resolved: bool) -> str:
    unit = _unit(instrument)
    if resolved:
        side = f"sous {threshold}{unit}" if direction == "above" else f"au-dessus de {threshold}{unit}"
        return f"{instrument} repassé {side} (valeur actuelle : {value}{unit})."
    verb = f"a dépassé {threshold}{unit}" if direction == "above" else f"est passé sous {threshold}{unit}"
    return f"{instrument} {verb} (valeur actuelle : {value}{unit})."


def evaluate_all_thresholds(db: Session) -> list[BondAlertEvent]:
    """Évalue chaque seuil activé contre la dernière valeur connue de son
    instrument, écrit un nouvel événement uniquement lors d'une transition
    de statut, et renvoie la liste des événements effectivement créés à cet
    appel (liste vide si rien n'a changé)."""
    latest_values = latest_value_by_instrument(db)
    created: list[BondAlertEvent] = []

    thresholds = db.execute(select(BondAlertThreshold).where(BondAlertThreshold.enabled.is_(True))).scalars().all()
    for threshold in thresholds:
        value = latest_values.get(threshold.instrument)
        if value is None:
            continue

        threshold_value = float(threshold.threshold_pct)
        crossed = _is_crossed(threshold.direction, value, threshold_value)
        last_event = db.execute(
            select(BondAlertEvent)
            .where(BondAlertEvent.threshold_id == threshold.id)
            .order_by(BondAlertEvent.triggered_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        currently_triggered = last_event is not None and last_event.status == "triggered"

        if crossed and not currently_triggered:
            event = BondAlertEvent(
                instrument=threshold.instrument,
                threshold_id=threshold.id,
                threshold_pct=threshold.threshold_pct,
                observed_value_pct=value,
                direction=threshold.direction,
                status="triggered",
                message=_format_message(threshold.instrument, threshold.direction, value, threshold_value, resolved=False),
            )
            db.add(event)
            created.append(event)
        elif not crossed and currently_triggered:
            event = BondAlertEvent(
                instrument=threshold.instrument,
                threshold_id=threshold.id,
                threshold_pct=threshold.threshold_pct,
                observed_value_pct=value,
                direction=threshold.direction,
                status="resolved",
                message=_format_message(threshold.instrument, threshold.direction, value, threshold_value, resolved=True),
            )
            db.add(event)
            created.append(event)

    db.commit()
    return created


def resolve_if_triggered(db: Session, threshold: BondAlertThreshold) -> BondAlertEvent | None:
    """Écrit un événement "resolved" si `threshold` est actuellement
    "triggered" — appelé explicitement quand un seuil est désactivé via
    `PATCH /bonds/alerts/thresholds/{id}` (`api/routers/bonds.py`).

    Sans cet appel explicite, désactiver un seuil (`enabled=False`) le
    sortirait silencieusement de `evaluate_all_thresholds` (qui ne regarde
    que les seuils actifs) sans jamais écrire l'événement "resolved" — la
    dernière alerte resterait affichée comme active indéfiniment, y compris
    après une éventuelle réactivation si la valeur sous-jacente est restée
    au-dessus du seuil entre-temps (aucune transition ne serait alors
    détectée à la réactivation). Ne commit pas lui-même — l'appelant gère sa
    propre transaction (voir `update_bond_alert_threshold`)."""
    last_event = db.execute(
        select(BondAlertEvent)
        .where(BondAlertEvent.threshold_id == threshold.id)
        .order_by(BondAlertEvent.triggered_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last_event is None or last_event.status != "triggered":
        return None

    event = BondAlertEvent(
        instrument=threshold.instrument,
        threshold_id=threshold.id,
        threshold_pct=threshold.threshold_pct,
        observed_value_pct=last_event.observed_value_pct,
        direction=threshold.direction,
        status="resolved",
        message=f"{threshold.instrument} : alerte désactivée manuellement (seuil {threshold.threshold_pct}"
        f"{_unit(threshold.instrument)}).",
    )
    db.add(event)
    return event
