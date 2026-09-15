"""Point d'entrée de l'API FastAPI (Phase 3).

Lancement (dev) :
    uvicorn api.main:app --reload

Documentation générée automatiquement par FastAPI : `/docs` (Swagger UI),
`/redoc`, et le schéma brut `/openapi.json`.
"""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from agents.mistral_client import MistralUnavailableError
from api.auth import SupabaseUnavailableError, require_user
from api.routers import agents, baskets, carry_trade, chat, decisions, energy, jane, news, portfolios, prices, reports, securities, share
from notifications.email_client import EmailUnavailableError

# Sans ceci, le niveau racine par défaut de Python (WARNING) rend tout
# `logger.info(...)` du projet (ex. `agents/chat.py`, `agents/jane_veille.py`
# en CLI) silencieusement invisible dans les logs Render — `logger.warning`/
# `.error`/`.exception` fonctionnaient déjà (d'où les handlers d'erreur
# existants jamais suspectés), ce qui a caché ce trou pendant longtemps.
# Trouvé en creusant pourquoi un log de diagnostic ajouté à `agents/chat.py`
# n'apparaissait jamais dans Render malgré un déploiement confirmé "Live".
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="George API",
    description="API de lecture pour l'agent d'analyse technique George (Phase 3) et couche LLM conversationnelle (Phase 4).",
    version="0.1.0",
)

# Authentification Supabase (Phase 9, portail simple — voir api/auth.py) :
# CORS limité au serveur de dev Vite en local ; à restreindre/remplacer avant
# tout déploiement partagé. `allow_headers=["*"]` couvre déjà l'en-tête
# `Authorization` envoyé par les clients authentifiés, aucun changement CORS
# supplémentaire n'est nécessaire pour ça.
# POST ajouté en Phase 4 pour /chat, /decisions/{id}/explanation, /reports ;
# DELETE ajouté pour /portfolios (suppression d'un portefeuille/d'une ligne).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Attrape spécifiquement les erreurs SQLAlchemy (base injoignable,
    requête invalide...) plutôt que la classe `Exception` nue : Starlette
    traite un handler enregistré pour `Exception` comme le handler de
    `ServerErrorMiddleware`, qui se trouve *au-dessus* de `CORSMiddleware`
    dans la pile — sa réponse ne repasse donc jamais par l'ajout des
    en-têtes CORS, et le navigateur voit une erreur CORS trompeuse au lieu
    du vrai message. Un handler sur une sous-classe précise comme
    `SQLAlchemyError` reste lui dans `ExceptionMiddleware`, *sous*
    `CORSMiddleware`, et récupère bien les en-têtes CORS."""
    logger.exception("Erreur base de données sur %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Base de données indisponible — voir les logs du serveur."})


@app.exception_handler(MistralUnavailableError)
async def mistral_exception_handler(request: Request, exc: MistralUnavailableError):
    """Même piège Starlette que ci-dessus (voir `database_exception_handler`) :
    une sous-classe précise plutôt que `Exception` nue, pour rester sous
    `CORSMiddleware`. Couvre la clé API manquante et le quota/rate limit
    épuisé après retries (Phase 4)."""
    logger.exception("Erreur API Mistral sur %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": f"Service LLM indisponible : {exc}"})


@app.exception_handler(SupabaseUnavailableError)
async def supabase_exception_handler(request: Request, exc: SupabaseUnavailableError):
    """Même piège Starlette que ci-dessus : une sous-classe précise plutôt
    que `Exception` nue, pour rester sous `CORSMiddleware`. Couvre la
    configuration Supabase manquante et le service d'authentification
    injoignable (Phase 9) — un jeton simplement invalide/expiré n'est PAS
    cette erreur, voir `api/auth.py:require_user`, qui lève une
    `HTTPException(401)` ordinaire (déjà gérée sous `CORSMiddleware` par le
    handler par défaut de Starlette, sans avoir besoin d'un handler dédié)."""
    logger.exception("Erreur d'authentification Supabase sur %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": f"Service d'authentification indisponible : {exc}"})


@app.exception_handler(EmailUnavailableError)
async def email_exception_handler(request: Request, exc: EmailUnavailableError):
    """Même piège Starlette que ci-dessus : une sous-classe précise plutôt
    que `Exception` nue, pour rester sous `CORSMiddleware`. Couvre la clé
    RESEND_API_KEY manquante, le service Resend injoignable, et un envoi
    refusé par Resend (ex. compte en bac à sable envoyant vers une adresse
    autre que celle du compte — voir `notifications/email_client.py`)."""
    logger.exception("Erreur d'envoi email sur %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": f"Service d'envoi d'email indisponible : {exc}"})


# `dependencies=[Depends(require_user)]` protège chaque route de ces 9
# routeurs sans que les fonctions de route aient à déclarer/consommer la
# dépendance elles-mêmes — ce portail simple (Phase 9) n'a besoin ni de
# filtrer les données par utilisateur, ni de faire remonter un identifiant
# aux routes, seule la présence d'un jeton Supabase valide compte. `/health`
# et les routes auto-générées par FastAPI (`/docs`, `/redoc`, `/openapi.json`)
# restent volontairement hors de cette liste.
app.include_router(securities.router, dependencies=[Depends(require_user)])
app.include_router(baskets.router, dependencies=[Depends(require_user)])
app.include_router(decisions.router, dependencies=[Depends(require_user)])
app.include_router(agents.router, dependencies=[Depends(require_user)])
app.include_router(chat.router, dependencies=[Depends(require_user)])
app.include_router(jane.router, dependencies=[Depends(require_user)])
app.include_router(reports.router, dependencies=[Depends(require_user)])
app.include_router(portfolios.router, dependencies=[Depends(require_user)])
app.include_router(prices.router, dependencies=[Depends(require_user)])
app.include_router(carry_trade.router, dependencies=[Depends(require_user)])
app.include_router(news.router, dependencies=[Depends(require_user)])
app.include_router(energy.router, dependencies=[Depends(require_user)])
app.include_router(share.router, dependencies=[Depends(require_user)])


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# TEMPORAIRE — diagnostic en direct d'un bug réel (graphique vide pour tous
# les titres, mobile ET web, alors que price_history_long est bien peuplée :
# vérifié via une action GitHub read-only, 255 785 lignes / 102 titres, 2587
# pour ETL.PA). Teste la MÊME connexion (`api.deps.engine`/`SessionLocal`)
# que `list_security_prices` en production, pas une connexion séparée — pour
# distinguer un problème de connexion DB (Render) d'un bug de requête/route.
# À supprimer une fois la cause trouvée.
@app.get("/debug/price-count/{symbol}", tags=["meta"])
def debug_price_count(symbol: str):
    from sqlalchemy import func, select

    from api import deps
    from ingestion.models import PriceHistoryLong

    with deps.SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(PriceHistoryLong))
        symbol_count = db.scalar(select(func.count()).select_from(PriceHistoryLong).where(PriceHistoryLong.symbol == symbol))
        latest = db.scalar(select(func.max(PriceHistoryLong.ts)).where(PriceHistoryLong.symbol == symbol))
    return {"symbol": symbol, "table_total_rows": total, "symbol_rows": symbol_count, "symbol_latest_ts": str(latest)}


# TEMPORAIRE — appelle la VRAIE fonction de route `list_security_prices`
# directement (même code, pas une réplique), avec le traceback complet
# capturé et renvoyé en JSON plutôt que transformé en 500 générique. Le
# précédent essai (une réplique manuelle de la requête) renvoyait lui-même
# une "Internal Server Error" brute sans passer par mon `try/except` --
# signe que l'échec se produit avant, donc plus la peine de deviner : on
# capture tout, y compris les erreurs d'import. À supprimer avec le reste.
@app.get("/debug/price-query/{symbol}", tags=["meta"])
def debug_price_query(symbol: str):
    import traceback

    try:
        from api import deps
        from api.routers.securities import list_security_prices

        with deps.SessionLocal() as db:
            result = list_security_prices(symbol, limit=250, offset=0, db=db)
        return {"ok": True, "total": result.total, "item_count": len(result.items)}
    except Exception as err:  # noqa: BLE001 -- diagnostic temporaire, on veut voir l'erreur telle quelle, y compris HTTPException/ImportError
        return {"ok": False, "error_type": type(err).__name__, "error": str(err), "traceback": traceback.format_exc()}
