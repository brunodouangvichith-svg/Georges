"""Endpoints `/agents` — flux d'activité des sous-agents de veille (Phase 7,
format carnet d'ordres) et déclenchement manuel d'une tâche de collecte
(`POST /collect`, MVP de la Phase 7 : pas de scheduler/Celery/Airflow encore,
même précédent que `POST /prices/refresh`)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.collectors import COLLECTORS
from agents.orchestrator import run_collection_task
from api import deps
from api.deps import get_db
from api.schemas import AgentEventOut, CollectionTaskRequest, CollectionTaskResponse, Page
from ingestion.models import AgentEvent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/activity", response_model=Page[AgentEventOut])
def list_agent_activity(
    status: str | None = Query(default=None, description="Filtrer par statut (validated, pending, quarantine)"),
    symbol: str | None = Query(default=None, description="Filtrer par titre"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(AgentEvent)
    if status is not None:
        stmt = stmt.where(AgentEvent.status == status)
    if symbol is not None:
        stmt = stmt.where(AgentEvent.symbol == symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(AgentEvent.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


@router.post("/collect", response_model=CollectionTaskResponse)
def trigger_collection(request: CollectionTaskRequest, db: Session = Depends(get_db)):
    if request.task_type not in COLLECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Type de tâche inconnu : {request.task_type}. Valeurs valides : {sorted(COLLECTORS)}",
        )
    if request.task_type == "synthese_document" and request.report_id is None:
        raise HTTPException(status_code=400, detail="report_id est requis pour task_type='synthese_document'.")
    if request.task_type == "donnees_finnhub" and request.symbol is None:
        raise HTTPException(status_code=400, detail="symbol est requis pour task_type='donnees_finnhub'.")
    if request.report_id is not None:
        scope = {"report_id": request.report_id}
    elif request.symbol is not None:
        scope = {"symbol": request.symbol}
    else:
        scope = None
    try:
        result = run_collection_task(db, deps.engine, request.task_type, COLLECTORS[request.task_type], scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CollectionTaskResponse(validated=result["validated"], quarantined_count=result["quarantined_count"])
