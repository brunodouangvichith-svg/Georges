import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


# 127.0.0.1 plutôt que "localhost" : ce dernier résout aussi en ::1, et
# psycopg essaie alors les deux adresses l'une après l'autre — quand rien
# n'écoute, ça double le temps avant l'échec (2 × CONNECT_TIMEOUT_SECONDS)
# pour rien, ce qui se voit particulièrement à l'usage derrière l'API
# (voir api/main.py:database_exception_handler) où chaque requête déjà
# retentée une fois par React Query s'ajoute par-dessus.
DEFAULT_DATABASE_URL = "postgresql+psycopg://george:george@127.0.0.1:5432/george"

# Sans timeout explicite, psycopg peut rester bloqué largement plus d'une
# minute quand rien n'écoute sur l'hôte/port — ce qui bloquerait
# silencieusement tout script attendant un échec rapide pour retomber sur un
# autre chemin (voir engine/notebooks/pattern_validation.ipynb).
CONNECT_TIMEOUT_SECONDS = 5


def get_database_url() -> str:
    raw = os.environ.get("DATABASE_URL")
    if raw is not None:
        # DEBUG TEMPORAIRE — diagnostic d'un échec de parsing SQLAlchemy sur
        # Render alors que la même chaîne parse correctement en local. Affiche
        # la forme de la valeur réellement injectée (sans le mot de passe en
        # clair) pour repérer un caractère invisible ajouté par le
        # copier-coller dans le dashboard Render (guillemets, saut de ligne,
        # espace). À retirer une fois le déploiement confirmé fonctionnel.
        print(
            "[DEBUG DATABASE_URL] "
            f"len={len(raw)} "
            f"repr_start={raw[:25]!r} "
            f"repr_end={raw[-25:]!r} "
            f"has_newline={chr(10) in raw or chr(13) in raw} "
            f"has_quote={chr(34) in raw or chr(39) in raw} "
            f"has_leading_trailing_space={raw != raw.strip()}"
        )
    return raw if raw is not None else DEFAULT_DATABASE_URL


def get_engine():
    return create_engine(
        get_database_url(),
        future=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def get_session_factory():
    return sessionmaker(bind=get_engine(), future=True)
