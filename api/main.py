"""Point d'entrée de l'API FastAPI (Phase 3).

Lancement (dev) :
    uvicorn api.main:app --reload

Documentation générée automatiquement par FastAPI : `/docs` (Swagger UI),
`/redoc`, et le schéma brut `/openapi.json`.
"""

import logging
import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from agents.mistral_client import MistralUnavailableError
from api.auth import SupabaseUnavailableError, require_user
from api.routers import (
    agents,
    baskets,
    bonds,
    chat,
    cron,
    decisions,
    energy,
    jane,
    news,
    portfolios,
    prices,
    reports,
    securities,
    share,
    strategic_reports,
)
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

# CORS : seules les origines listées dans `CORS_EXTRA_ORIGINS` sont autorisées
# (en production : le site george-web sur Render). Plus aucune origine
# localhost par défaut depuis la mise en ligne du web (oct. 2026) — pour
# relancer le serveur de dev Vite contre une API locale, exporter
# `CORS_EXTRA_ORIGINS=http://localhost:5173` avant `uvicorn`.
# `allow_headers=["*"]` couvre l'en-tête `Authorization` des clients
# authentifiés. POST : /chat, /reports… ; PATCH : seuils Obligataire ;
# DELETE : /portfolios. Les applis natives (Flutter) ne sont pas concernées
# par CORS, qui ne s'applique qu'aux navigateurs.


def cors_origins() -> list[str]:
    """Origines autorisées, lues dans `CORS_EXTRA_ORIGINS` (séparées par des
    virgules) au démarrage de l'API ; espaces et `/` final ignorés, car
    l'en-tête `Origin` d'un navigateur n'en a jamais."""
    origins: list[str] = []
    for raw in os.environ.get("CORS_EXTRA_ORIGINS", "").split(","):
        origin = raw.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # PATCH : seuils Obligataire Watch (web)
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
app.include_router(news.router, dependencies=[Depends(require_user)])
app.include_router(energy.router, dependencies=[Depends(require_user)])
app.include_router(share.router, dependencies=[Depends(require_user)])
app.include_router(bonds.router, dependencies=[Depends(require_user)])
app.include_router(strategic_reports.router, dependencies=[Depends(require_user)])
# Pas de `dependencies=[Depends(require_user)]` ici, volontairement — voir
# le docstring de `api/routers/cron.py` : ce routeur a sa propre dépendance
# (`require_cron_secret`, secret partagé plutôt qu'une session Supabase).
app.include_router(cron.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
