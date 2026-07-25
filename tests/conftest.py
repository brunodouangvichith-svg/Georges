import pytest
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    """Instance TimescaleDB jetable (nécessite un démon Docker local)."""
    with PostgresContainer(
        image="timescale/timescaledb:latest-pg16",
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
