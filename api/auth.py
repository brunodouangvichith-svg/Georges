"""Portail d'authentification simple (Phase 9) — Supabase Auth utilisé
uniquement comme fournisseur d'identité : aucune table applicative de
George ne vit côté Supabase, et cette dépendance ne fait qu'autoriser
l'accès (décisions/paniers/portefeuilles restent globaux/partagés, pas
d'isolation par utilisateur).

Jamais de décodage JWT local : le jeton est toujours vérifié par un vrai
appel à `{SUPABASE_URL}/auth/v1/user`, portage direct d'un mécanisme déjà
validé en production dans un projet frère (`MeteoIA/db.py:obtenir_utilisateur`).
Même principe que `agents/mistral_client.py:_get_client()` : les variables
d'environnement sont lues à l'appel, jamais à l'import, pour que ce module
reste importable/testable sans clé configurée.
"""

import os

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class SupabaseUnavailableError(RuntimeError):
    """Configuration Supabase manquante ou service injoignable — classe
    dédiée (pas `Exception` nue) pour que `api/main.py` lui enregistre un
    handler FastAPI spécifique restant sous `CORSMiddleware`, même piège
    Starlette que `SQLAlchemyError`/`MistralUnavailableError` (voir
    CLAUDE.md, section Phase 3). Un jeton simplement invalide/expiré n'est
    PAS cette erreur : voir `require_user`, qui lève une `HTTPException(401)`
    ordinaire pour ce cas, déjà gérée par le handler par défaut de
    Starlette sous `CORSMiddleware`."""


_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_supabase_token(token: str) -> dict | None:
    """Vérifie un jeton Supabase par un vrai appel HTTP (jamais de décodage
    JWT local). Renvoie `None` pour un jeton invalide/expiré (cas normal),
    lève `SupabaseUnavailableError` seulement si la configuration manque ou
    si Supabase est injoignable."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_anon_key:
        raise SupabaseUnavailableError("Variables d'environnement SUPABASE_URL/SUPABASE_ANON_KEY manquantes.")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": supabase_anon_key},
            )
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError(f"Service d'authentification Supabase injoignable : {exc}") from exc

    if response.status_code != 200:
        return None
    return response.json()


async def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> str:
    """Dépendance branchée au niveau de chaque routeur (`dependencies=` sur
    `app.include_router(...)`, voir `api/main.py`) plutôt que sur chaque
    route individuellement : ce portail simple n'a besoin ni de filtrer les
    données par utilisateur, ni de faire remonter l'identifiant à la route —
    seule la présence d'un jeton Supabase valide compte. `auto_error=False`
    sur `HTTPBearer` puis une `HTTPException(401)` levée à la main (plutôt
    que le comportement par défaut, qui renvoie un 403 trompeur pour un
    en-tête manquant)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentification requise.", headers={"WWW-Authenticate": "Bearer"})

    user = await verify_supabase_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée.", headers={"WWW-Authenticate": "Bearer"})

    return user["id"]
