"""Pytest fixtures: a fresh set of tables per test session against a real
PostgreSQL database (never SQLite), plus a FastAPI TestClient wired to it.

Requires a reachable PostgreSQL instance. By default it uses the same
DATABASE_URL as the application but swaps the database name to
'codsp_test_db' so tests never touch developer/production data. Override
with TEST_DATABASE_URL if you need something else.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core import database as db_module
from app.core.config import get_settings


def _build_test_url(base_url: str) -> str:
    if "/codsp_db" in base_url:
        return base_url.replace("/codsp_db", "/codsp_test_db")
    return base_url.rsplit("/", 1)[0] + "/codsp_test_db"


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    test_url = os.environ.get("TEST_DATABASE_URL", _build_test_url(settings.database_url))

    admin_url = test_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    db_name = test_url.rsplit("/", 1)[1]
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": db_name}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    engine = create_engine(test_url, future=True)

    # Import all models so metadata is fully populated, then create tables
    # directly for test speed (Alembic migrations are exercised separately;
    # see test_migrations-equivalent coverage via the app import chain).
    from app.modules.audit import models as _audit  # noqa: F401
    from app.modules.constraints import models as _constraints  # noqa: F401
    from app.modules.daily_stock import models as _daily_stock  # noqa: F401
    from app.modules.documents import models as _documents  # noqa: F401
    from app.modules.landed_cost import models as _landed_cost  # noqa: F401
    from app.modules.master_data import models as _master_data  # noqa: F401
    from app.modules.optimization import models as _optimization  # noqa: F401
    from app.modules.recommendations import models as _recommendations  # noqa: F401

    db_module.Base.metadata.drop_all(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = TestSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[db_module.get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def unique_code():
    return uuid.uuid4().hex[:8].upper()
