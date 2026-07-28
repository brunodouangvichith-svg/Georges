"""Endpoints `/portfolios` — portefeuilles nommés choisis manuellement par
l'investisseur à partir d'un sous-ensemble de `decisions` (web/, écran « Mon
Portefeuille ») — voir `ingestion/models.py:Portfolio` pour la distinction
avec le `Report` de portée `"portfolio"` (Phase 4)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import deps
from api.deps import get_db
from api.schemas import (
    AllocateBudgetRequest,
    AllocateBudgetResponse,
    PortfolioCreateRequest,
    PortfolioDecisionOut,
    PortfolioOut,
)
from engine.portfolio_allocation import allocate_budget, format_allocation_summary
from engine.reevaluate_decisions import BULLISH_DECISIONS
from engine.run_detection import load_prices
from ingestion.models import Decision, Portfolio, PortfolioDecision

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _portfolio_decisions(db: Session, portfolio_id: int) -> list[tuple[Decision, int | None]]:
    return (
        db.execute(
            select(Decision, PortfolioDecision.quantity)
            .join(PortfolioDecision, PortfolioDecision.decision_id == Decision.id)
            .where(PortfolioDecision.portfolio_id == portfolio_id)
            .order_by(Decision.created_at.desc())
        )
        .all()
    )


def _current_price_and_pnl(engine, decision: Decision) -> tuple[float | None, float | None]:
    """Prix le plus récent et rendement (%) courant depuis l'entrée, même
    logique direction-consciente (Achat/Renforcer haussier, Alléger baissier)
    que `engine.reevaluate_decisions.evaluate_decision` — mais calculé
    directement sur le dernier cours plutôt qu'en réutilisant cette fonction :
    son filtre `since = df[df.index >= decision.created_at]` sert à borner
    l'historique pour la détection de franchissement TP/SL (Phase 6), pas au
    calcul d'un PnL affiché en direct, et renvoie `None` tant qu'aucune
    séance n'est postérieure à la création — pour une décision prise sur la
    clôture du jour même, cela laisse le PnL vide jusqu'à la séance
    suivante alors que le rendement (nul ce jour-là) est déjà connu.
    `pnl_pct` reste `None` seulement si aucun prix n'est disponible du tout."""
    df = load_prices(engine, decision.symbol)
    if df.empty:
        return None, None
    current_price = float(df["close"].iloc[-1])
    entry = float(decision.entry_price)
    direction = 1 if decision.decision_type in BULLISH_DECISIONS else -1
    pnl_pct = (current_price - entry) / entry * 100 * direction
    return current_price, pnl_pct


def _portfolio_out(db: Session, engine, portfolio: Portfolio) -> PortfolioOut:
    rows = _portfolio_decisions(db, portfolio.id)
    decisions = []
    total_pnl_amount = 0.0
    total_invested = 0.0
    has_any_position = False

    for decision, quantity in rows:
        current_price, pnl_pct = _current_price_and_pnl(engine, decision)
        decisions.append(
            PortfolioDecisionOut.model_validate(decision, from_attributes=True).model_copy(
                update={"quantity": quantity, "current_price": current_price, "pnl_pct": pnl_pct}
            )
        )
        if quantity and pnl_pct is not None:
            invested = quantity * float(decision.entry_price)
            total_invested += invested
            total_pnl_amount += invested * pnl_pct / 100
            has_any_position = True

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        decisions=decisions,
        total_pnl_amount=round(total_pnl_amount, 2) if has_any_position else None,
        total_invested=round(total_invested, 2) if has_any_position else None,
    )


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(db: Session = Depends(get_db)):
    portfolios = db.execute(select(Portfolio).order_by(Portfolio.created_at.desc())).scalars().all()
    return [_portfolio_out(db, deps.engine, p) for p in portfolios]


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
    return _portfolio_out(db, deps.engine, portfolio)


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
    return _portfolio_out(db, deps.engine, portfolio)


@router.post("/{portfolio_id}/allocate", response_model=AllocateBudgetResponse)
def allocate_portfolio_budget(portfolio_id: int, request: AllocateBudgetRequest, db: Session = Depends(get_db)):
    """Répartit un budget entre les décisions du portefeuille — action
    « Demander à George » de `web/` (ex. "répartis un budget de 100 000
    euros entre ces actions en fonction du risque et des profits"). Le
    calcul est entièrement déterministe (`engine/portfolio_allocation.py`) ;
    aucun appel LLM ici, voir le docstring de ce module pour le raisonnement."""
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"Portefeuille inconnu : {portfolio_id}")
    if request.budget <= 0:
        raise HTTPException(status_code=400, detail="Le budget doit être positif.")

    rows = _portfolio_decisions(db, portfolio_id)
    if not rows:
        raise HTTPException(status_code=400, detail="Ce portefeuille est vide, rien à répartir.")

    decisions_for_alloc = [
        {
            "decision_id": decision.id,
            "symbol": decision.symbol,
            "entry_price": float(decision.entry_price),
            "stop_loss": float(decision.stop_loss) if decision.stop_loss is not None else None,
            "take_profit": float(decision.take_profit) if decision.take_profit is not None else None,
            "confidence": float(decision.confidence),
        }
        for decision, _quantity in rows
    ]
    allocations = allocate_budget(decisions_for_alloc, request.budget)

    for alloc in allocations:
        link = db.get(PortfolioDecision, {"portfolio_id": portfolio_id, "decision_id": alloc["decision_id"]})
        link.quantity = alloc["quantity"]
    db.commit()

    summary = format_allocation_summary(decisions_for_alloc, allocations, request.budget)
    return AllocateBudgetResponse(portfolio=_portfolio_out(db, deps.engine, portfolio), summary=summary)
