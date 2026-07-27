"""Endpoints `/reports` — génération et recherche sémantique de rapports
automatiques (Phase 4, tâches 4-5). Voir `agents/reports.py`."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.reports import generate_report, search_reports
from api import deps
from api.deps import get_db
from api.schemas import Page, ReportOut, ReportRequest
from ingestion.models import Report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=Page[ReportOut])
def list_reports(
    basket_id: int | None = Query(default=None, description="Filtrer par panier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Report)
    if basket_id is not None:
        stmt = stmt.where(Report.basket_id == basket_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Report.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


@router.get("/search", response_model=list[ReportOut])
def search(
    q: str = Query(description="Requête en langage naturel — recherche sémantique via pgvector"),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return search_reports(db, q, limit)


@router.post("", response_model=ReportOut)
def create_report(request: ReportRequest, db: Session = Depends(get_db)):
    try:
        # `deps.engine` résolu dynamiquement (pas un import figé) — voir
        # `api/routers/baskets.py` pour le bug de référence obsolète que ce
        # pattern évite (CLAUDE.md, section Phase 3).
        return generate_report(db, deps.engine, request.basket_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
