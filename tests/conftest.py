import pytest
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    """Instance Postgres jetable (nécessite un démon Docker local).

    Postgres classique, pas TimescaleDB : les migrations n'en dépendent
    plus (voir CLAUDE.md — l'extension timescaledb n'est pas disponible sur
    Supabase, l'hébergeur Postgres géré gratuit visé pour George). Image
    `pgvector/pgvector:pg17` plutôt que `postgres:17` nu : pgvector était
    fourni gratuitement par l'ancienne image TimescaleDB, migration `0004`
    en a besoin (`CREATE EXTENSION vector`) — confirmé en perdant cette
    extension au premier essai avec `postgres:17` seul. Version 17 pour
    matcher exactement celle de Supabase.
    """
    with PostgresContainer(
        image="pgvector/pgvector:pg17",
        username="george",
        password="george",
        dbname="george",
    ) as container:
        yield container


@pytest.fixture()
def database_url(postgres_container, monkeypatch):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    url = f"postgresql+psycopg://george:george@{host}:{port}/george"
    monkeypatch.setenv("DATABASE_URL", url)
    return url
