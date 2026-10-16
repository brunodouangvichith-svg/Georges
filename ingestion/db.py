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


# Pool volontairement petit : la base Supabase (instance Nano, plan gratuit)
# n'accepte que peu de connexions via le Session pooler, où chaque connexion
# ouverte côté George occupe une place. Le défaut SQLAlchemy (5 + 10 par
# processus) permettait à l'API seule d'en prendre 15 pendant un chargement
# de l'Univers (~200 requêtes d'un coup), en plus des jobs GitHub Actions.
# 2 + 2 suffit : les requêtes sont courtes et les autres attendent leur tour
# (POOL_TIMEOUT_SECONDS) au lieu de saturer la base. Surchargeable par
# DB_POOL_SIZE / DB_MAX_OVERFLOW sans redéploiement de code.
DEFAULT_POOL_SIZE = 2
DEFAULT_MAX_OVERFLOW = 2
POOL_TIMEOUT_SECONDS = 30
# Recycler les connexions avant que le pooler Supabase ne les coupe de son
# côté, et vérifier chaque connexion avant usage (pool_pre_ping) : après un
# redémarrage du projet Supabase, les connexions gardées en pool sont mortes
# (« Connection reset by peer ») et feraient échouer la requête suivante.
POOL_RECYCLE_SECONDS = 300


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _int_env(name: str, default: int, minimum: int) -> int:
    """Entier lu dans l'environnement ; valeur absente ou invalide -> défaut."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def get_engine():
    return create_engine(
        get_database_url(),
        future=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_size=_int_env("DB_POOL_SIZE", DEFAULT_POOL_SIZE, minimum=1),
        max_overflow=_int_env("DB_MAX_OVERFLOW", DEFAULT_MAX_OVERFLOW, minimum=0),
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,
    )


def get_session_factory():
    return sessionmaker(bind=get_engine(), future=True)
