from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import Base, get_db
from app.main import app  # importing the app also registers every table
from app.models import InviteCode

TEST_DB_NAME = "expenses_test"

dev_url = make_url(get_settings().DATABASE_URL)
test_url = dev_url.set(database=TEST_DB_NAME)


def create_test_database() -> None:
    # CREATE DATABASE can't run inside a transaction, hence AUTOCOMMIT.
    admin_engine = create_engine(dev_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    create_test_database()
    engine = create_engine(test_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A direct DB session for setting up or inspecting rows in tests."""
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with engine.begin() as conn:
        # Every table, emptied before each test; CASCADE follows the foreign keys.
        conn.execute(
            text(
                "TRUNCATE expenses, refresh_tokens, invite_codes, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    TestSessionLocal = sessionmaker(bind=engine, autoflush=False)

    def get_test_db() -> Iterator[Session]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_expense(client: TestClient) -> Callable[..., dict]:
    def _make(**overrides) -> dict:
        body = {
            "amount": "4.50",
            "currency": "GBP",
            "date": "2026-10-15",
            "merchant": "Chatime",
            "category": "Food",
        } | overrides
        response = client.post("/expenses", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def make_invite(client: TestClient, db_session: Session) -> Callable[[], str]:
    """Create a fresh, unused invite code and return it."""
    counter = iter(range(1, 1000))

    def _make() -> str:
        code = f"TEST-{next(counter):04d}"
        db_session.add(InviteCode(code=code))
        db_session.commit()
        return code

    return _make
