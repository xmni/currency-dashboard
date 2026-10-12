"""Shared test fixtures.

Tests run against a real PostgreSQL:
- If TEST_DATABASE_URL is set, that database is used.
- Otherwise a throwaway Postgres starts in Docker (testcontainers) and is removed after.
"""

import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, get_db
from app.main import app
from app.market import models  # noqa: F401  (registers tables on Base.metadata)
from app.market.models import Asset
from app.market.provider import ProviderRate
from app.market.router import get_provider


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url)
        Base.metadata.drop_all(eng)
        Base.metadata.create_all(eng)
        yield eng
        eng.dispose()
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="psycopg") as pg:
        eng = create_engine(pg.get_connection_url())
        Base.metadata.create_all(eng)
        yield eng
        eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session for one test; all tables are emptied afterwards."""
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE rate_snapshots, assets RESTART IDENTITY CASCADE"))


class FakeProvider:
    """Stands in for the real API so tests are fast and don't need the internet."""

    name = "fake"

    def __init__(self) -> None:
        self.rates: list[ProviderRate] = []

    def fetch_rates(
        self,
        base: str,
        quotes: list[str],
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderRate]:
        return self.rates


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(db: Session, fake_provider: FakeProvider) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_provider] = lambda: fake_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def usd_eur(db: Session) -> None:
    db.add_all([Asset(code="USD", name="US Dollar"), Asset(code="EUR", name="Euro")])
    db.commit()


def rate(day: str, value: str) -> ProviderRate:
    return ProviderRate("USD", "EUR", Decimal(value), date.fromisoformat(day))