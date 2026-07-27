"""Endpoints `/securities` — référentiel des titres, leurs figures
détectées et leur historique de prix.

`GET /securities/{symbol}/prices` n'est pas dans la liste minimale
d'endpoints du prompt de la Phase 3, mais est indispensable au graphique en
chandeliers du panneau de détail (tâche 6) : sans historique de prix, il
n'y a rien à tracer. Ajouté au-delà du minimum plutôt que de contourner le
problème côté front.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import Page, PatternOut, PriceBarOut, SecurityOut
from ingestion.models import BasketSecurity, PatternDetected, PriceOHLCV, Security

router = APIRouter(prefix="/securities", tags=["securities"])


def _get_security_or_404(symbol: str, db: Session) -> Security:
    security = db.get(Security, symbol)
    if security is None:
        raise HTTPException(status_code=404, detail=f"Titre inconnu : {symbol}")
    return security


@router.get("", response_model=Page[SecurityOut])
def list_securities(
    basket_id: int | None = Query(default=None, description="Filtrer par panier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Security)
    if basket_id is not None:
        stmt = stmt.join(BasketSecurity, BasketSecurity.symbol == Security.symbol).where(
            BasketSecurity.basket_id == basket_id
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Security.symbol).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


@router.get("/{symbol}/patterns", response_model=Page[PatternOut])
def list_security_patterns(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _get_security_or_404(symbol, db)
    stmt = select(PatternDetected).where(PatternDetected.symbol == symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    # Un même run de détection confirme souvent plusieurs figures pour un
    # même titre avec le même `detected_at` (toutes sur la dernière séance) —
    # sans second critère de tri, l'ordre entre ces ex-aequo n'est pas
    # garanti et peut renvoyer n'importe laquelle en `limit=1` (constaté :
    # la figure la moins confiante systématiquement première). La confiance
    # décroissante départage de façon significative plutôt qu'arbitraire.
    rows = (
        db.execute(
            stmt.order_by(PatternDetected.detected_at.desc(), PatternDetected.confidence.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


@router.get("/{symbol}/prices", response_model=Page[PriceBarOut])
def list_security_prices(
    symbol: str,
    limit: int = Query(default=250, ge=1, le=2000, description="Nombre de séances les plus récentes"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Les `limit` séances les plus récentes (au-delà de `offset`),
    renvoyées en ordre chronologique croissant — prêtes pour un graphique."""
    _get_security_or_404(symbol, db)
    stmt = select(PriceOHLCV).where(PriceOHLCV.symbol == symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(PriceOHLCV.ts.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=list(reversed(rows)), total=total or 0, limit=limit, offset=offset)
