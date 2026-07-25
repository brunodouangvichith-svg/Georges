import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://george:george@localhost:5432/george"

# Sans timeout explicite, psycopg peut rester bloqué largement plus d'une
# minute (essais IPv6 puis IPv4) quand rien n'écoute sur l'hôte/port —
# ce qui bloquerait silencieusement tout script attendant un échec rapide
# pour retomber sur un autre chemin (voir engine/notebooks/pattern_validation.ipynb).
CONNECT_TIMEOUT_SECONDS = 5


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine():
    return create_engine(
        get_database_url(),
        future=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def get_session_factory():
    return sessionmaker(bind=get_engine(), future=True)
