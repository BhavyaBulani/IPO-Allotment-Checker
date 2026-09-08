"""Shared pytest fixtures.

Two kinds of tests live here:

- **No-DB tests** (auth, token/security, registrar parsers) run everywhere and
  never touch a database. They use ``app_client``.
- **DB-backed tests** (results export, batch summary, history) need a real
  MySQL because the SQLAlchemy models use ``BigInteger`` auto-increment primary
  keys, which SQLite does not auto-populate. They use ``db_client`` and are
  skipped automatically unless ``TEST_DATABASE_URL`` is set — locally via
  ``docker-compose up -d``, or in CI via the MySQL service container.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def app_client():
    """A TestClient that does NOT run the app lifespan.

    Instantiating without a ``with`` block keeps FastAPI from starting the
    background IPO-sync / DB-keepalive tasks, which would try to reach a live
    MySQL and the public registrar sites during a plain unit-test run.
    """
    from main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set; skipping database-backed tests")

    from db.models import Base

    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A fresh, empty set of tables per test for isolation."""
    from db.models import Base

    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)

    session = sessionmaker(bind=db_engine)()
    yield session
    session.close()


@pytest.fixture
def db_client(db_engine, db_session):
    """A TestClient whose ``get_db`` dependency is bound to the test session."""
    from main import app
    from db.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
