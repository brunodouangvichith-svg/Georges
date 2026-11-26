"""Endpoints `/securities` — référentiel des titres, leurs figures
détectées et leur historique de prix.

`GET /securities/{symbol}/prices` n'est pas dans la liste minimale
d'endpoints du prompt de la Phase 3, mais est indispensable au graphique en
chandeliers du panneau de détail (tâche 6) : sans historique de prix, il
n'y a rien à tracer. Ajouté au-delà du minimum plutôt que de contourner le
problème côté front.
"""

import datetime
import threading
import time

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import (
    DividendOut,
    FundamentalsOut,
    IndexReferenceOut,
    Page,
    PatternOut,
    PriceBarOut,
    RiskMetricsOut,
    SecurityOut,
)
from engine.risk_metrics import PARIS, compute_risk_metrics
from engine.run_detection import load_recent_prices
from ingestion import index_prices
from ingestion.models import BasketSecurity, CompanyFundamentals, Dividend, PatternDetected, PriceHistoryLong, Security

router = APIRouter(prefix="/securities", tags=["securities"])

# Assez pour 253 clôtures (un an de rendements) avec une marge pour les trous.
RISK_HISTORY_DAYS = 550
# Quelques secondes de calcul pour tout l'univers, sur des cours qui changent
# rarement : le résultat est gardé en mémoire (un seul worker uvicorn). Vidé par
# « Mise à jour des prix » ; un import programmé est vu à l'expiration.
RISK_CACHE_SECONDS = 300
_risk_lock = threading.Lock()
_risk_cache: dict = {"value": None, "expires_at": 0.0}


def clear_risk_cache() -> None:
    with _risk_lock:
        _risk_cache.update(value=None, expires_at=0.0)


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


@router.get("/patterns/latest", response_model=list[PatternOut])
def list_latest_patterns(db: Session = Depends(get_db)):
    """Dernière figure de chaque titre, en une seule requête — pour le radar
    de l'écran Univers (web et mobile), qui sinon fait un appel
    `/{symbol}/patterns?limit=1` par titre (~100 requêtes, chacune avec sa
    connexion, qui saturaient le petit pool de l'API et faisaient échouer
    les autres requêtes sur « QueuePool limit … reached »). Même règle de
    départage que `list_security_patterns` : date puis confiance
    décroissantes. Un titre sans figure n'apparaît pas."""
    ranked = select(
        PatternDetected.id,
        func.row_number()
        .over(
            partition_by=PatternDetected.symbol,
            order_by=(PatternDetected.detected_at.desc(), PatternDetected.confidence.desc()),
        )
        .label("rn"),
    ).subquery()
    stmt = (
        select(PatternDetected)
        .join(ranked, ranked.c.id == PatternDetected.id)
        .where(ranked.c.rn == 1)
        .order_by(PatternDetected.symbol)
    )
    return db.execute(stmt).scalars().all()


@router.get("/risk-metrics", response_model=RiskMetricsOut)
def list_risk_metrics(db: Session = Depends(get_db)):
    """Liquidité et risque de tout l'univers (`engine/risk_metrics.py`), calculés
    à la demande avec une seule lecture des prix — jamais un appel par titre."""
    # Le verrou évite deux calculs simultanés ; la session ne prend une
    # connexion qu'à sa première requête, donc l'attente n'en bloque aucune.
    with _risk_lock:
        if time.monotonic() >= _risk_cache["expires_at"]:
            value = _build_risk_metrics(db)
            _risk_cache.update(value=value, expires_at=time.monotonic() + RISK_CACHE_SECONDS)
        return _risk_cache["value"]


def _build_risk_metrics(db: Session) -> RiskMetricsOut:
    # Avant toute requête : aucune connexion du pool n'attend Yahoo.
    index_close = index_prices.cac40_closes()
    now = pd.Timestamp.now(tz=PARIS)
    sectors = {row.symbol: row.sector for row in db.execute(select(Security.symbol, Security.sector))}
    since = now.to_pydatetime() - datetime.timedelta(days=RISK_HISTORY_DAYS)
    prices = load_recent_prices(db.connection(), since)
    today = now.tz_localize(None).normalize()
    if index_close is not None:
        index_close = index_close[index_close.index < today]
    available = index_close is not None and not index_close.empty
    return RiskMetricsOut(
        index=IndexReferenceOut(
            name=index_prices.INDEX_NAME,
            ticker=index_prices.INDEX_TICKER,
            available=available,
            as_of=index_close.index[-1].date() if available else None,
        ),
        items=compute_risk_metrics(prices, sectors, index_close, today),
    )


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


@router.get("/{symbol}/fundamentals", response_model=FundamentalsOut)
def get_security_fundamentals(symbol: str, db: Session = Depends(get_db)):
    """Instantané le plus récent (`observed_at` décroissant) — pas de
    `Page[T]`, une seule ligne. `404` si l'import quotidien
    (`ingestion.fundamentals`) n'a encore jamais tourné pour ce titre."""
    _get_security_or_404(symbol, db)
    row = db.execute(
        select(CompanyFundamentals)
        .where(CompanyFundamentals.symbol == symbol)
        .order_by(CompanyFundamentals.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Aucun instantané fondamentaux pour {symbol}.")
    return row


@router.get("/{symbol}/dividends", response_model=Page[DividendOut])
def list_security_dividends(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _get_security_or_404(symbol, db)
    stmt = select(Dividend).where(Dividend.symbol == symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Dividend.ex_date.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=rows, total=total or 0, limit=limit, offset=offset)


@router.get("/{symbol}/prices", response_model=Page[PriceBarOut])
def list_security_prices(
    symbol: str,
    limit: int = Query(default=250, ge=1, le=3000, description="Nombre de séances les plus récentes"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Les `limit` séances les plus récentes (au-delà de `offset`),
    renvoyées en ordre chronologique croissant — prêtes pour un graphique.
    Lit `price_history_long` (jusqu'à 10 ans) plutôt que `prices_ohlcv`
    (2 ans, plus alimentée depuis le passage à `price_history_long` — voir
    CLAUDE.md) ; `le=3000` couvre large les ~2600 séances de 10 ans, contre
    2000 (~8 ans) auparavant."""
    _get_security_or_404(symbol, db)
    stmt = select(PriceHistoryLong).where(PriceHistoryLong.symbol == symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(PriceHistoryLong.ts.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=list(reversed(rows)), total=total or 0, limit=limit, offset=offset)
