"""Endpoints `/bonds` — Obligataire Watch (ad hoc, pas une phase du
roadmap). Liste brute pour l'historique (pas de `Page[T]`, même choix que
`/baskets`) ; réutilise directement `engine.compute_bond_yields`/
`engine.bond_alerts`/`engine.bond_bulletin` plutôt que de redupliquer les
calculs ici."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import (
    BondAlertEventOut,
    BondAlertThresholdOut,
    BondAlertThresholdUpdateRequest,
    BondBulletinOut,
    BondCollectionRunOut,
    BondDashboardOut,
    BondRefreshResponse,
    BondYieldHistoryPointOut,
)
from engine.bond_alerts import evaluate_all_thresholds, resolve_if_triggered
from engine.bond_bulletin import generate_daily_bulletin
from engine.compute_bond_yields import build_dashboard_summary, load_history
from ingestion import bond_yields
from ingestion.models import BondAlertEvent, BondAlertThreshold, BondCollectionRun

router = APIRouter(prefix="/bonds", tags=["bonds"])


@router.get("", response_model=BondDashboardOut)
def get_bond_dashboard(db: Session = Depends(get_db)):
    return build_dashboard_summary(db)


@router.get("/{instrument}/history", response_model=list[BondYieldHistoryPointOut])
def get_bond_history(
    instrument: str,
    limit: int = Query(default=365, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    snapshots = load_history(db, instrument, limit=limit)
    return [BondYieldHistoryPointOut(observed_at=s.observed_at, value_pct=float(s.value_pct)) for s in snapshots]


@router.get("/alerts/thresholds", response_model=list[BondAlertThresholdOut])
def list_bond_alert_thresholds(db: Session = Depends(get_db)):
    return db.execute(select(BondAlertThreshold).order_by(BondAlertThreshold.instrument)).scalars().all()


@router.patch("/alerts/thresholds/{threshold_id}", response_model=BondAlertThresholdOut)
def update_bond_alert_threshold(
    threshold_id: int, request: BondAlertThresholdUpdateRequest, db: Session = Depends(get_db)
):
    """Modifie un seuil existant sans toucher au code, comme demandé
    explicitement par le cahier des charges §8. Ne crée jamais de nouveau
    seuil — les 3 seuils initiaux (`ingestion/seed_bond_alert_thresholds.py`,
    exécuté au déploiement) sont la seule façon d'en ajouter en V1.

    Désactiver un seuil actuellement "triggered" écrit immédiatement un
    événement "resolved" (`engine.bond_alerts.resolve_if_triggered`) — sinon
    la dernière alerte resterait affichée comme active indéfiniment, y
    compris après une éventuelle réactivation (voir le docstring de cette
    fonction pour le détail du bug que ça évite)."""
    threshold = db.get(BondAlertThreshold, threshold_id)
    if threshold is None:
        raise HTTPException(status_code=404, detail=f"Seuil inconnu : {threshold_id}")
    # `resolve_if_triggered` doit tourner avant la mise à jour de
    # `threshold_pct` : il lit `threshold.threshold_pct` pour l'événement
    # "resolved" qu'il écrit, et un PATCH changeant threshold_pct et enabled
    # dans le même appel enregistrerait sinon le nouveau seuil plutôt que
    # celui réellement franchi (trouvé par /code-review).
    if request.enabled is not None:
        threshold.enabled = request.enabled
        if not request.enabled:
            resolve_if_triggered(db, threshold)
    if request.threshold_pct is not None:
        threshold.threshold_pct = request.threshold_pct
    threshold.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(threshold)
    return threshold


@router.get("/alerts/events", response_model=list[BondAlertEventOut])
def list_bond_alert_events(
    status: str | None = Query(default=None, description="Filtrer par statut (triggered, resolved)"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(BondAlertEvent).order_by(BondAlertEvent.triggered_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(BondAlertEvent.status == status)
    return db.execute(stmt).scalars().all()


@router.get("/collection-runs", response_model=list[BondCollectionRunOut])
def list_bond_collection_runs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    """État technique de la collecte (cahier des charges §9.D : dernière
    collecte réussie, erreurs) — les lignes les plus récentes en premier."""
    stmt = select(BondCollectionRun).order_by(BondCollectionRun.started_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/bulletin", response_model=BondBulletinOut)
def get_daily_bulletin(db: Session = Depends(get_db)):
    return BondBulletinOut(bulletin=generate_daily_bulletin(db), generated_at=datetime.datetime.now(datetime.timezone.utc))


@router.post("/refresh", response_model=BondRefreshResponse)
def refresh_bonds(db: Session = Depends(get_db)):
    """Déclenchement manuel de la collecte + réévaluation des seuils —
    route synchrone (Banque de France, Bundesbank, FRED : quelques appels rapides, contrairement à
    `POST /prices/refresh` qui tourne en tâche de fond) ; planification
    automatique via
    `.github/workflows/daily_bond_yields.yml`, pas de scheduler Celery/Redis
    (Phase 7 non câblée, voir CLAUDE.md)."""
    summary = bond_yields.run()
    db.expire_all()  # `bond_yields.run()` écrit via un Engine séparé, même précaution que `/decisions/propose`
    created_alerts = evaluate_all_thresholds(db)
    return BondRefreshResponse(
        instruments_updated=sorted(i for i, ok in summary.items() if ok),
        instruments_failed=sorted(i for i, ok in summary.items() if not ok),
        alerts_created=len(created_alerts),
    )
