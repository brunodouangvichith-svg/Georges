"""Endpoints `/portfolios` — portefeuilles nommés choisis manuellement par
l'investisseur à partir d'un sous-ensemble de `decisions` (web/, écran « Mon
Portefeuille ») — voir `ingestion/models.py:Portfolio` pour la distinction
avec le `Report` de portée `"portfolio"` (Phase 4)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import PortfolioCreateRequest, PortfolioOut
from ingestion.models import Decision, Portfolio, PortfolioDecision

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _portfolio_out(db: Session, portfolio: Portfolio) -> PortfolioOut:
    decisions = (
        db.execute(
            select(Decision)
            .join(PortfolioDecision, PortfolioDecision.decision_id == Decision.id)
            .where(PortfolioDecision.portfolio_id == portfolio.id)
            .order_by(Decision.created_at.desc())
        )
        .scalars()
        .all()
    )
    return PortfolioOut(id=portfolio.id, name=portfolio.name, created_at=portfolio.created_at, decisions=decisions)


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(db: Session = Depends(get_db)):
    portfolios = db.execute(select(Portfolio).order_by(Portfolio.created_at.desc())).scalars().all()
    return [_portfolio_out(db, p) for p in portfolios]


@router.post("", response_model=PortfolioOut)
def create_portfolio(request: PortfolioCreateRequest, db: Session = Depends(get_db)):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Le nom du portefeuille ne peut pas être vide.")
    if not request.decision_ids:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins une décision.")

    known_ids = set(
        db.execute(select(Decision.id).where(Decision.id.in_(request.decision_ids))).scalars().all()
    )
    unknown_ids = set(request.decision_ids) - known_ids
    if unknown_ids:
        raise HTTPException(status_code=404, detail=f"Décision(s) inconnue(s) : {sorted(unknown_ids)}")

    portfolio = Portfolio(name=request.name.strip())
    db.add(portfolio)
    db.flush()  # attribue portfolio.id avant d'insérer les liens
    db.add_all(PortfolioDecision(portfolio_id=portfolio.id, decision_id=did) for did in request.decision_ids)
    db.commit()
    return _portfolio_out(db, portfolio)


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"Portefeuille inconnu : {portfolio_id}")
    db.delete(portfolio)  # ON DELETE CASCADE supprime les lignes portfolio_decisions liées
    db.commit()


@router.delete("/{portfolio_id}/decisions/{decision_id}", response_model=PortfolioOut)
def remove_decision_from_portfolio(portfolio_id: int, decision_id: int, db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"Portefeuille inconnu : {portfolio_id}")

    link = db.get(PortfolioDecision, {"portfolio_id": portfolio_id, "decision_id": decision_id})
    if link is None:
        raise HTTPException(status_code=404, detail="Cette décision n'est pas dans ce portefeuille.")
    db.delete(link)
    db.commit()
    return _portfolio_out(db, portfolio)
