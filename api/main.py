"""Point d'entrée de l'API FastAPI (Phase 3).

Lancement (dev) :
    uvicorn api.main:app --reload

Documentation générée automatiquement par FastAPI : `/docs` (Swagger UI),
`/redoc`, et le schéma brut `/openapi.json`.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from api.routers import agents, baskets, decisions, securities

logger = logging.getLogger(__name__)

app = FastAPI(
    title="George API",
    description="API de lecture pour l'agent d'analyse technique George (Phase 3).",
    version="0.1.0",
)

# Pas d'authentification à ce stade (voir Phase 9) — CORS limité au serveur
# de dev Vite en local ; à restreindre/remplacer avant tout déploiement partagé.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
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


app.include_router(securities.router)
app.include_router(baskets.router)
app.include_router(decisions.router)
app.include_router(agents.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
