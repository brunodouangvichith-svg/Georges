"""Endpoint `/agents/activity` — flux d'activité des sous-agents de veille
(Phase 7), format carnet d'ordres. `agent_events` est vide jusqu'à ce que la
Phase 7 construise les sous-agents qui l'alimentent."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import AgentEventOut, Page
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
