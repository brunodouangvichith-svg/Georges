"""Endpoint `/prices/refresh` — déclenche le téléchargement des prix
(`ingestion.price_history.run`) depuis l'écran Univers (bouton « Mise à jour
des prix » de la sidebar). Repointé de `ingestion.ohlcv.run` (`prices_ohlcv`,
2 ans) vers `price_history_long` (10 ans) en même temps que
`engine.run_detection.load_prices` — sinon ce bouton aurait continué à
rafraîchir une table que plus aucun code ne lit, silencieusement inerte du
point de vue de l'utilisateur.

**Asynchrone depuis ce changement** (le passage à 10 ans avait rendu
l'ancien appel synchrone systématiquement plus long que le timeout HTTP
mobile de 2 min, `mobile/lib/data/prices_refresh_repository.dart` — le vrai
correctif est ici, pas un timeout mobile encore plus long) : `POST /refresh`
planifie le travail via `BackgroundTasks` et répond immédiatement avec le
statut ; les clients font ensuite un `GET /refresh` en polling jusqu'à
`status in {"done", "failed"}`. État en mémoire (`_state`, un seul worker
uvicorn ici — voir CLAUDE.md section Hosting — pas besoin de Redis/Celery
pour un seul job à la fois) protégé par `_lock` contre un déclenchement
concurrent : un `POST` alors qu'un job tourne déjà renvoie simplement le
statut `"running"` courant plutôt que d'en empiler un second. Aucune tâche
planifiée à fréquence fine n'existe encore (Celery/Redis, Airflow — Phase 7)
; ce bouton reste le seul moyen de rafraîchir manuellement en dehors du cron
bihebdomadaire (`price_history_and_detection.yml`, lundi/mercredi) ou de
`python -m ingestion.price_history` en ligne de commande."""

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from api.schemas import PriceRefreshStatus
from ingestion.price_history import run as run_price_refresh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["prices"])

_lock = threading.Lock()
_state: dict = {"status": "idle"}


def _run_refresh_job() -> None:
    """Exécuté par `BackgroundTasks` après la réponse du `POST` — jamais sur
    la requête HTTP elle-même. Capture toute exception plutôt que de la
    laisser remonter : ce code tourne hors de tout contexte de requête, une
    exception non attrapée ici ne serait vue par personne et laisserait
    `_state` bloqué sur `"running"` indéfiniment."""
    global _state
    try:
        summary = run_price_refresh()
        failed = sorted(symbol for symbol, rows in summary.items() if rows < 0)
        updated = sorted(symbol for symbol, rows in summary.items() if rows >= 0)
        with _lock:
            _state = {
                "status": "done",
                "started_at": _state.get("started_at"),
                "finished_at": datetime.now(timezone.utc),
                "total": len(summary),
                "updated_count": len(updated),
                "failed_symbols": failed,
            }
    except Exception as exc:  # noqa: BLE001 - job de fond : doit atterrir dans le statut, jamais crasher silencieusement
        logger.exception("Le rafraîchissement des prix a échoué")
        with _lock:
            _state = {
                "status": "failed",
                "started_at": _state.get("started_at"),
                "finished_at": datetime.now(timezone.utc),
                "error": str(exc),
            }


@router.post("/refresh", response_model=PriceRefreshStatus)
def refresh_prices(background_tasks: BackgroundTasks):
    """Idempotent tant qu'un job tourne : ne relance jamais un second
    rafraîchissement en parallèle, renvoie juste l'état du job en cours.

    `global _state` déclaré explicitement même si `.clear()`/`.update()` sont
    des mutations en place qui n'en ont pas strictement besoin aujourd'hui
    (contrairement à `_run_refresh_job`, qui réassigne `_state` en entier) —
    sans cette déclaration, un futur refactor vers une réassignation directe
    (`_state = {...}`, la forme la plus naturelle et déjà utilisée dans
    `_run_refresh_job`) ferait de `_state` une variable locale dans cette
    fonction, provoquant un `UnboundLocalError` immédiat dès `_state.get(...)`
    quelques lignes plus bas."""
    global _state
    with _lock:
        if _state.get("status") == "running":
            return PriceRefreshStatus(**_state)
        _state.clear()
        _state.update({"status": "running", "started_at": datetime.now(timezone.utc)})
        state_snapshot = dict(_state)
    background_tasks.add_task(_run_refresh_job)
    return PriceRefreshStatus(**state_snapshot)


@router.get("/refresh", response_model=PriceRefreshStatus)
def refresh_status():
    """Polling côté client (web et mobile) jusqu'à `status in {"done",
    "failed"}` — voir web/src/api/queries.js:useRefreshPrices et
    mobile/lib/data/prices_refresh_repository.dart."""
    with _lock:
        return PriceRefreshStatus(**_state)
