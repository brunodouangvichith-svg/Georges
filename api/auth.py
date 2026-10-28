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

import hmac
import logging
import os

import httpx
from fastapi import Depends, Header, HTTPException
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

logger = logging.getLogger(__name__)

# Délai par tentative et nombre de tentatives pour l'appel à Supabase Auth.
# Octobre 2026 : depuis Render, l'appel dépassait parfois l'ancien délai de
# 5 s (premières connexions sortantes lentes juste après un réveil), ce qui
# renvoyait un 503 au navigateur alors que Supabase répondait en 0,1 s depuis
# ailleurs. Une seconde tentative ne sert que pour une erreur de transport
# (délai, connexion) — jamais pour une réponse HTTP, qui dit déjà si le jeton
# est valide.
SUPABASE_TIMEOUT_SECONDS = 10.0
SUPABASE_MAX_ATTEMPTS = 2


async def verify_supabase_token(token: str) -> dict | None:
    """Vérifie un jeton Supabase par un vrai appel HTTP (jamais de décodage
    JWT local). Renvoie `None` pour un jeton invalide/expiré (cas normal),
    lève `SupabaseUnavailableError` seulement si la configuration manque ou
    si Supabase est injoignable."""
    # `.strip()` : une valeur collée dans le tableau de bord Render peut
    # garder un retour à la ligne invisible, qui casserait l'URL construite.
    supabase_url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    supabase_anon_key = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not supabase_url or not supabase_anon_key:
        raise SupabaseUnavailableError("Variables d'environnement SUPABASE_URL/SUPABASE_ANON_KEY manquantes.")

    url = f"{supabase_url}/auth/v1/user"
    headers = {"Authorization": f"Bearer {token}", "apikey": supabase_anon_key}
    response = None
    async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT_SECONDS) as client:
        for attempt in range(1, SUPABASE_MAX_ATTEMPTS + 1):
            try:
                response = await client.get(url, headers=headers)
                break
            except httpx.TransportError as exc:
                # Le type exact (ConnectTimeout, ReadTimeout, ConnectError…) est
                # le vrai diagnostic : `str(exc)` est souvent vide pour un délai
                # dépassé, d'où le message vide observé en production.
                logger.warning(
                    "Supabase Auth injoignable (tentative %d/%d) : %s %r",
                    attempt,
                    SUPABASE_MAX_ATTEMPTS,
                    type(exc).__name__,
                    exc,
                )
                if attempt == SUPABASE_MAX_ATTEMPTS:
                    raise SupabaseUnavailableError(
                        f"Service d'authentification Supabase injoignable ({type(exc).__name__}: {exc})"
                    ) from exc
            except httpx.HTTPError as exc:
                raise SupabaseUnavailableError(
                    f"Service d'authentification Supabase injoignable ({type(exc).__name__}: {exc})"
                ) from exc

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


def require_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    """Dépendance dédiée à `api/routers/cron.py`, séparée de `require_user` à
    dessein : ces routes sont appelées machine-à-machine (le Worker
    Cloudflare qui a remplacé les jobs planifiés GitHub Actions, voir
    CLAUDE.md, section Cron Cloudflare) et n'ont donc pas de session
    Supabase à présenter — leur faire passer `require_user` obligerait à
    fabriquer/rafraîchir un faux compte utilisateur juste pour un appel
    serveur-à-serveur, sans aucun bénéfice (ce portail ne fait de toute
    façon aucun filtrage par utilisateur, voir le docstring de module).

    Comparaison à temps constant (`hmac.compare_digest`) plutôt que `==` :
    une comparaison naïve fuiterait la longueur du préfixe correct par
    timing, un risque réel pour un secret HTTP comparé à chaque appel
    planifié. `CRON_SECRET` est lu à l'appel (jamais à l'import), même
    principe que `SUPABASE_URL`/`SUPABASE_ANON_KEY` ci-dessus. Une variable
    manquante lève un 500 (erreur de configuration serveur, pas une faute
    de l'appelant) plutôt que de réutiliser `SupabaseUnavailableError`, qui
    produirait un message trompeur ("service d'authentification Supabase
    indisponible") pour un problème sans rapport avec Supabase."""
    expected = (os.environ.get("CRON_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="Variable d'environnement CRON_SECRET manquante côté serveur.")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=401, detail="Secret cron invalide ou manquant.")
