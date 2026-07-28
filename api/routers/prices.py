"""Endpoint `/prices/refresh` — déclenche manuellement le téléchargement des
prix OHLCV (`ingestion.ohlcv.run`, Phase 1) depuis l'écran Univers (bouton
« Mise à jour des prix » de la sidebar). Aucune tâche planifiée n'existe
encore (Celery/Redis, Airflow — Phase 7) ; c'est le seul moyen de rafraîchir
`prices_ohlcv` en dehors de relancer `python -m ingestion.ohlcv` en ligne de
commande."""

from fastapi import APIRouter

from api.schemas import PriceRefreshResponse
from ingestion.ohlcv import run as run_price_refresh

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/refresh", response_model=PriceRefreshResponse)
def refresh_prices():
    """Route définie en `def`, pas `async def` : FastAPI l'exécute alors
    dans son threadpool par défaut plutôt que sur la boucle asyncio, ce qui
    évite qu'un appel synchrone et potentiellement long (~une minute pour
    tout l'univers CAC 40 + Mid 60, réseau + retries yfinance inclus) ne
    bloque les autres requêtes en cours. Reste un appel bloquant du point de
    vue du client HTTP qui l'a déclenché — acceptable pour une action
    manuelle occasionnelle, pas pour une tâche planifiée à haute fréquence."""
    summary = run_price_refresh()
    failed = sorted(symbol for symbol, rows in summary.items() if rows < 0)
    updated = sorted(symbol for symbol, rows in summary.items() if rows >= 0)
    return PriceRefreshResponse(total=len(summary), updated_count=len(updated), failed_symbols=failed)
