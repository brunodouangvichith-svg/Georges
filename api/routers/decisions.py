"""Endpoint `/decisions` — décisions proposées par George (jamais exécutées
automatiquement), filtrables par statut et par panier. Inclut aussi
`/decisions/{id}/explanation` (Phase 4, tâches 1 et « second avis » de
Jane) — voir `agents/explainer.py` et `agents/jane.py`."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.explainer import explain_decision
from agents.jane import second_opinion
from api.deps import get_db
from api.schemas import DecisionOut, ExplanationRequest, ExplanationResponse, Page
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


@router.post("/{decision_id}/explanation", response_model=ExplanationResponse)
def get_decision_explanation(
    decision_id: int,
    request: ExplanationRequest,
    db: Session = Depends(get_db),
):
    """`include_second_opinion=true` appelle d'abord Jane (second appel LLM
    distinct, `mistral-large-latest`) puis passe sa note comme contexte
    supplémentaire à l'explication de George — implémentation du hook
    « Jane relit le dossier complet avant que George ne publie sa décision »
    de la roadmap (Phase 4/6), sans dépendre d'un pipeline de publication
    automatique de décisions qui n'existe pas encore (Phase 6)."""
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Décision inconnue : {decision_id}")

    jane_note = second_opinion(db, decision) if request.include_second_opinion else None
    explanation = explain_decision(db, decision, jane_note)
    return ExplanationResponse(explanation=explanation, second_opinion=jane_note)
