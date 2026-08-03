"""Endpoint `/prices/refresh` — déclenche manuellement le téléchargement des
prix (`ingestion.price_history.run`) depuis l'écran Univers (bouton « Mise à
jour des prix » de la sidebar). Repointé de `ingestion.ohlcv.run`
(`prices_ohlcv`, 2 ans) vers `price_history_long` (10 ans) en même temps que
`engine.run_detection.load_prices` — sinon ce bouton aurait continué à
rafraîchir une table que plus aucun code ne lit, silencieusement inerte du
point de vue de l'utilisateur. Aucune tâche planifiée à fréquence fine
n'existe encore (Celery/Redis, Airflow — Phase 7) ; ce bouton reste le seul
moyen de rafraîchir manuellement en dehors du cron hebdomadaire
(`weekly_price_history_import.yml`) ou de `python -m ingestion.price_history`
en ligne de commande."""

from fastapi import APIRouter

from api.schemas import PriceRefreshResponse
from ingestion.price_history import run as run_price_refresh

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/refresh", response_model=PriceRefreshResponse)
def refresh_prices():
    """Route définie en `def`, pas `async def` : FastAPI l'exécute alors
    dans son threadpool par défaut plutôt que sur la boucle asyncio, ce qui
    évite qu'un appel synchrone et potentiellement long (10 ans d'historique
    par titre sur tout l'univers CAC 40 + Mid 60, réseau + retries yfinance
    inclus — plus long que le rafraîchissement 2 ans d'avant ce changement)
    ne bloque les autres requêtes en cours. Reste un appel bloquant du point
    de vue du client HTTP qui l'a déclenché — acceptable pour une action
    manuelle occasionnelle, pas pour une tâche planifiée à haute fréquence."""
    summary = run_price_refresh()
    failed = sorted(symbol for symbol, rows in summary.items() if rows < 0)
    updated = sorted(symbol for symbol, rows in summary.items() if rows >= 0)
    return PriceRefreshResponse(total=len(summary), updated_count=len(updated), failed_symbols=failed)
