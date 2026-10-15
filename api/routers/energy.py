"""Endpoint `/energy-prices` — dernier instantané connu de chaque matière
première suivie (Brent, WTI, gaz naturel, produits raffinés), alimenté par
`ingestion/energy_prices.py` (OilPriceAPI, import quotidien planifié via
GitHub Actions). Liste brute, pas de `Page[T]` — même précédent que
`GET /baskets` (6 lignes au maximum)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import EnergyPriceOut
from ingestion.models import EnergyPriceSnapshot

router = APIRouter(prefix="/energy-prices", tags=["energy"])


@router.get("", response_model=list[EnergyPriceOut])
def list_energy_prices(db: Session = Depends(get_db)):
    """`DISTINCT ON (commodity_code)` (spécifique Postgres, déjà le seul
    moteur ciblé par ce projet) trié par `snapshot_date` décroissant : la
    ligne la plus récente par matière première, pas tout l'historique."""
    stmt = (
        select(EnergyPriceSnapshot)
        .distinct(EnergyPriceSnapshot.commodity_code)
        .order_by(EnergyPriceSnapshot.commodity_code, EnergyPriceSnapshot.snapshot_date.desc())
    )
    return db.execute(stmt).scalars().all()
