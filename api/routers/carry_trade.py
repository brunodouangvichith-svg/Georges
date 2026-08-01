"""Endpoints `/carry-trade` — panier Carry Trade (ad hoc, pas une phase du
roadmap). Liste brute (pas de `Page[T]`), même choix que `/baskets` — ce
n'est pas un univers de la taille de `securities`. Réutilise directement
`engine.carry_index`/`engine.compute_carry_index` plutôt que de redupliquer
le calcul de score ici — même principe que `api/routers/baskets.py` pour le
George Index."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.explainer import explain_carry_trade
from api import deps
from api.deps import get_db
from api.schemas import CarryPairOut, CarryTradeDetailOut, CarryTradeExplanationResponse, CarryTradeRefreshResponse
from engine.carry_index import compute_carry_score
from engine.compute_carry_index import latest_cot_by_currency, latest_rate_by_currency, load_fx_prices
from ingestion import carry_rates, cot_positioning, fx_rates
from ingestion.models import CurrencyPair

router = APIRouter(prefix="/carry-trade", tags=["carry-trade"])


def _score_pair(pair: CurrencyPair, rates: dict, cot: dict):
    # `deps.engine`, pas un `engine` importé nommément à la volée — même
    # précaution anti-référence-figée que `baskets.py` (voir CLAUDE.md).
    fx_prices = load_fx_prices(deps.engine, pair.symbol)
    score = compute_carry_score(
        funding_rate_pct=rates.get(pair.funding_currency),
        target_rate_pct=rates.get(pair.target_currency),
        fx_prices=fx_prices if not fx_prices.empty else None,
        cot=cot.get(pair.funding_currency),
    )
    scored = {
        "symbol": pair.symbol,
        "name": pair.name,
        "funding_currency": pair.funding_currency,
        "target_currency": pair.target_currency,
        "funding_rate_pct": rates.get(pair.funding_currency),
        "target_rate_pct": rates.get(pair.target_currency),
        **score,
    }
    return scored, fx_prices


@router.get("", response_model=list[CarryPairOut])
def list_carry_trade(db: Session = Depends(get_db)):
    pairs = db.execute(select(CurrencyPair).order_by(CurrencyPair.symbol)).scalars().all()
    rates = latest_rate_by_currency(deps.engine)
    cot = latest_cot_by_currency(deps.engine)
    return [_score_pair(pair, rates, cot)[0] for pair in pairs]


@router.get("/{symbol}", response_model=CarryTradeDetailOut)
def get_carry_trade_detail(symbol: str, db: Session = Depends(get_db)):
    pair = db.get(CurrencyPair, symbol)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"Paire inconnue : {symbol}")
    rates = latest_rate_by_currency(deps.engine)
    cot = latest_cot_by_currency(deps.engine)
    scored, fx_prices = _score_pair(pair, rates, cot)
    recent_prices = [
        {
            "ts": ts.to_pydatetime(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        }
        for ts, row in fx_prices.tail(60).iterrows()
    ]
    return CarryTradeDetailOut(**scored, recent_prices=recent_prices)


@router.post("/{symbol}/explanation", response_model=CarryTradeExplanationResponse)
def explain_carry_trade_pair(symbol: str, db: Session = Depends(get_db)):
    pair = db.get(CurrencyPair, symbol)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"Paire inconnue : {symbol}")
    rates = latest_rate_by_currency(deps.engine)
    cot = latest_cot_by_currency(deps.engine)
    scored, _ = _score_pair(pair, rates, cot)
    return CarryTradeExplanationResponse(explanation=explain_carry_trade(scored))


@router.post("/refresh", response_model=CarryTradeRefreshResponse)
def refresh_carry_trade():
    """Déclenchement manuel des 3 flux d'ingestion (prix FX, taux, COT) —
    même précédent que `POST /prices/refresh` : route sync (pas de tâche
    planifiée, Celery/Redis non câblés, voir Phase 7), acceptable pour une
    action manuelle occasionnelle."""
    fx_summary = fx_rates.run()
    rate_summary = carry_rates.run()
    cot_summary = cot_positioning.run()
    return CarryTradeRefreshResponse(
        fx_prices_updated=len([s for s, v in fx_summary.items() if v >= 0]),
        fx_prices_failed=sorted(s for s, v in fx_summary.items() if v < 0),
        rates_updated=sorted(c for c, v in rate_summary.items() if v),
        rates_failed=sorted(c for c, v in rate_summary.items() if not v),
        cot_updated=sorted(c for c, v in cot_summary.items() if v),
        cot_failed=sorted(c for c, v in cot_summary.items() if not v),
    )
