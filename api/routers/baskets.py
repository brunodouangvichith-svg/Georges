"""Endpoints `/baskets` — paniers et leur George Index.

Le calcul du George Index réutilise directement `engine.george_index`
(Phase 2) plutôt que de le redupliquer ici — l'API est un client de plus du
même module que les scripts `engine/compute_george_index.py`."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import deps
from api.deps import get_db
from api.schemas import BasketOut, GeorgeIndexOut
from engine.compute_george_index import load_patterns
from engine.george_index import compute_george_index
from engine.run_detection import load_prices
from ingestion.models import Basket, BasketSecurity

router = APIRouter(prefix="/baskets", tags=["baskets"])


@router.get("", response_model=list[BasketOut])
def list_baskets(db: Session = Depends(get_db)):
    return db.execute(select(Basket).order_by(Basket.name)).scalars().all()


@router.get("/{basket_id}/george-index", response_model=GeorgeIndexOut)
def get_basket_george_index(basket_id: int, db: Session = Depends(get_db)):
    basket = db.get(Basket, basket_id)
    if basket is None:
        raise HTTPException(status_code=404, detail=f"Panier inconnu : {basket_id}")

    links = db.execute(select(BasketSecurity).where(BasketSecurity.basket_id == basket_id)).scalars().all()
    basket_symbols = [(link.symbol, float(link.weight) if link.weight is not None else 1.0) for link in links]

    # `deps.engine`, pas un `engine` importé nommément à la volée : ce
    # dernier fige la référence au moment de l'import et ne verrait jamais
    # un `monkeypatch.setattr(deps, "engine", ...)` fait après coup (piège
    # rencontré en testant contre une vraie base — voir tests/test_api.py).
    patterns = load_patterns(deps.engine)
    price_frames = {symbol: load_prices(deps.engine, symbol) for symbol, _ in basket_symbols}
    price_frames = {symbol: df for symbol, df in price_frames.items() if not df.empty}

    index = compute_george_index(basket_symbols, patterns, price_frames, datetime.now(timezone.utc))
    return GeorgeIndexOut(basket_id=basket.id, basket_name=basket.name, george_index=index)
