from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.tests.db import (
    make_postgres_test_client,
    postgres_test_database_url,
    reset_postgres_test_database,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    database_url = postgres_test_database_url()

    with make_postgres_test_client() as test_client:
        yield test_client

    reset_postgres_test_database(database_url)
