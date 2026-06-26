import os

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from backend.app.database import Base, create_sqlalchemy_engine
from backend.app.main import create_app


def postgres_test_database_url() -> str:
    database_url = os.getenv("HABI_TEST_DATABASE_URL")
    if database_url is None:
        raise RuntimeError(
            "Set HABI_TEST_DATABASE_URL to a dedicated Postgres test database URL."
        )

    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise RuntimeError("HABI_TEST_DATABASE_URL must use a Postgres database.")

    return database_url


def reset_postgres_test_database(database_url: str) -> None:
    engine = create_sqlalchemy_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    engine.dispose()


def make_postgres_test_client() -> TestClient:
    database_url = postgres_test_database_url()
    reset_postgres_test_database(database_url)
    return TestClient(create_app(database_url=database_url))
