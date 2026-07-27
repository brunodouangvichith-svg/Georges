"""Endpoint `/decisions` — décisions proposées par George (jamais exécutées
automatiquement), filtrables par statut et par panier."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import DecisionOut, Page
from ingestion.models import BasketSecurity, Decision

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=Page[DecisionOut])
def list_decisions(
    status: str | None = Query(
        default=None, description="Filtrer par type de décision (Achat, Renforcer, Surveiller, Alléger)"
    ),
    basket_id: int | None = Query(default=None, description="Filtrer par panier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Decision)
    if status is not None:
        stmt = stmt.where(Decision.decision_type == status)
    if basket_id is not None:
        stmt = stmt.join(BasketSecurity, BasketSecurity.symbol == Decision.symbol).where(
            BasketSecurity.basket_id == basket_id
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Decision.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)
