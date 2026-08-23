"""Endpoint `/decisions` — décisions proposées par George (jamais exécutées
automatiquement), filtrables par type et par panier. Inclut aussi
`/decisions/{id}/explanation` (Phase 4, tâches 1 et « second avis » de
Jane, voir `agents/explainer.py`/`agents/jane.py`) et tout le cycle de vie
proposition -> confirmation -> sortie de la Phase 6 (`propose`,
`propose-levels`, `confirm`, `monitor`, `confirm-exit`) — voir
`engine/propose_decisions.py` et `engine/monitor_decisions.py`."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

import engine.monitor_decisions as monitor_decisions
import engine.propose_decisions as propose_decisions
from agents.explainer import explain_decision
from agents.jane import reformulate_formal, second_opinion
from api import deps
from api.deps import get_db
from api.schemas import ConfirmDecisionRequest, DecisionOut, ExplanationRequest, ExplanationResponse, JaneSecondOpinionOut, Page
from engine.reevaluate_decisions import evaluate_decision
from engine.run_detection import load_prices
from ingestion.models import Decision, BasketSecurity, DecisionOutcome, JaneSecondOpinion, PatternDetected

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=Page[DecisionOut])
def list_decisions(
    decision_type: str | None = Query(
        default=None, description="Filtrer par type de décision (Achat, Renforcer, Surveiller, Alléger)"
    ),
    status: str | None = Query(
        default=None, description="Filtrer par statut de cycle de vie (proposee, confirmee, sortie_proposee, cloturee)"
    ),
    basket_id: int | None = Query(default=None, description="Filtrer par panier"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Decision)
    if decision_type is not None:
        stmt = stmt.where(Decision.decision_type == decision_type)
    if status is not None:
        stmt = stmt.where(Decision.status == status)
    if basket_id is not None:
        stmt = stmt.join(BasketSecurity, BasketSecurity.symbol == Decision.symbol).where(
            BasketSecurity.basket_id == basket_id
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Decision.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


def _get_decision_or_404(decision_id: int, db: Session) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Décision inconnue : {decision_id}")
    return decision


@router.post("/propose", response_model=list[DecisionOut])
def propose(db: Session = Depends(get_db)):
    """Scanne les figures actives à forte confiance sans décision déjà
    ouverte et crée une proposition par titre qualifiant (`status="proposee"`)
    — voir `engine/propose_decisions.py`. Rien n'est confirmé
    automatiquement."""
    created = propose_decisions.run()
    if not created:
        return []
    db.expire_all()  # `run()` écrit via un Engine séparé — invalider le cache ORM avant de relire
    ids = [c["id"] for c in created]
    return db.execute(select(Decision).where(Decision.id.in_(ids))).scalars().all()


@router.post("/{decision_id}/propose-levels", response_model=DecisionOut)
def propose_levels_endpoint(decision_id: int, db: Session = Depends(get_db)):
    """Recalcule take-profit/stop-loss d'une décision encore `"proposee"` sur
    le prix le plus récent (tâche 2 de la Phase 6) — n'a de sens que tant
    qu'elle n'a pas été confirmée."""
    decision = _get_decision_or_404(decision_id, db)
    if decision.status != "proposee":
        raise HTTPException(status_code=409, detail=f"Décision {decision_id} n'est plus au statut 'proposee'.")
    if decision.pattern_id is None:
        raise HTTPException(status_code=400, detail="Aucune figure rattachée à cette décision, niveaux non recalculables.")

    pattern = db.get(PatternDetected, decision.pattern_id)
    take_profit, stop_loss = propose_decisions.recompute_levels(
        deps.engine, decision.symbol, pattern.pattern_type, pattern.context
    )
    decision.take_profit = take_profit
    decision.stop_loss = stop_loss
    db.commit()
    return decision


@router.post("/{decision_id}/confirm", response_model=DecisionOut)
def confirm(decision_id: int, request: ConfirmDecisionRequest, db: Session = Depends(get_db)):
    """Valide une décision `"proposee"` — l'investisseur peut ajuster
    take-profit/stop-loss dans le corps de la requête avant confirmation
    (tâche 3 de la Phase 6)."""
    decision = _get_decision_or_404(decision_id, db)
    if decision.status != "proposee":
        raise HTTPException(status_code=409, detail=f"Décision {decision_id} n'est plus au statut 'proposee'.")

    if request.take_profit is not None:
        decision.take_profit = request.take_profit
    if request.stop_loss is not None:
        decision.stop_loss = request.stop_loss
    decision.status = "confirmee"
    db.commit()
    return decision


@router.post("/monitor", response_model=list[DecisionOut])
def monitor(db: Session = Depends(get_db)):
    """Déclenche le job de suivi (tâche 4 de la Phase 6) : pour chaque
    décision confirmée dont le cours a franchi take-profit/stop-loss,
    propose un scénario de sortie et sa justification (`status` passe à
    `"sortie_proposee"`) — voir `engine/monitor_decisions.py`. Ne clôture
    jamais une position elle-même (voir la contrainte de la roadmap)."""
    proposed = monitor_decisions.run()
    if not proposed:
        return []
    db.expire_all()
    ids = [p["id"] for p in proposed]
    return db.execute(select(Decision).where(Decision.id.in_(ids))).scalars().all()


@router.post("/{decision_id}/confirm-exit", response_model=DecisionOut)
def confirm_exit(decision_id: int, db: Session = Depends(get_db)):
    """Valide le scénario de sortie proposé par le job de suivi — seule
    action qui clôture réellement une décision : écrit dans
    `decision_outcomes` (tâche 5, alimente le réentraînement du modèle,
    Phase 2) et passe `status` à `"cloturee"`."""
    decision = _get_decision_or_404(decision_id, db)
    if decision.status != "sortie_proposee":
        raise HTTPException(status_code=409, detail=f"Décision {decision_id} n'a pas de sortie proposée en attente.")

    # Recalculée plutôt que reconstruite depuis `exit_scenario` : la cause
    # réelle (take-profit ou stop-loss) doit être identifiée sans ambiguïté
    # pour `decision_outcomes` (tâche 5) — `exit_scenario` ("sortie_totale")
    # ne suffit pas seul à la retrouver, un stop-loss confirmé par le volume
    # produit lui aussi une "sortie_totale".
    df = load_prices(deps.engine, decision.symbol)
    outcome = evaluate_decision(decision, df)
    if outcome is None or outcome[0] == "open":
        raise HTTPException(status_code=409, detail="Le niveau franchi n'est plus vérifiable sur l'historique actuel.")
    result, pnl_pct, _hit_at = outcome

    db.add(
        DecisionOutcome(
            decision_id=decision.id,
            evaluated_at=datetime.now(timezone.utc),
            result=result,
            pnl_pct=pnl_pct,
        )
    )
    decision.status = "cloturee"
    db.commit()
    return decision


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
    de la roadmap (Phase 4/6). Fonctionne aussi bien sur une décision
    illustrative (`seed_demo.py`) que sur une décision réellement proposée
    par `engine.propose_decisions` (Phase 6, endpoint `/decisions/propose`).

    L'explication finale passe ensuite systématiquement (indépendamment de
    `include_second_opinion`) par `agents.jane.reformulate_formal` -- un
    rôle sans rapport avec le second avis ci-dessus, demandé directement par
    l'utilisateur pour que l'écran « George explique » utilise un registre
    plus formel. `second_opinion` (la note contradictoire de Jane, si
    demandée) n'est en revanche jamais reformulée : elle reste la relecture
    brute de Jane, distincte de l'explication finale de George."""
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Décision inconnue : {decision_id}")

    jane_note = second_opinion(db, decision) if request.include_second_opinion else None
    explanation = explain_decision(db, decision, jane_note)
    explanation = reformulate_formal(explanation)
    return ExplanationResponse(explanation=explanation, second_opinion=jane_note)


@router.get("/{decision_id}/second-opinions", response_model=Page[JaneSecondOpinionOut])
def list_second_opinions(
    decision_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Historique des notes de second avis de Jane pour une décision
    (`agents.jane.second_opinion`, persistées depuis l'ajout de
    `jane_second_opinions`) — une décision peut en accumuler plusieurs au
    fil de son cycle de vie, jamais une seule figée. Pensé pour une future
    évaluation de la pertinence de Jane en recroisant ce contenu avec
    `decision_outcomes` (même `decision_id`), pas encore construite."""
    _get_decision_or_404(decision_id, db)
    stmt = select(JaneSecondOpinion).where(JaneSecondOpinion.decision_id == decision_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(JaneSecondOpinion.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)
