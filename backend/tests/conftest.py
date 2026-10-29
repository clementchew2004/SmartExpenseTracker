from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token, hash_password
from app.config import get_settings
from app.db import Base, get_db
from app.main import app  # importing the app also registers every table
from app.models import InviteCode, User

TEST_DB_NAME = "expenses_test"

# Hashed once: Argon2 is deliberately slow, and most tests need a user.
TEST_PASSWORD_HASH = hash_password("correct horse")

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
def anon_client(engine: Engine) -> Iterator[TestClient]:
    """A client with no login, on an empty test database."""
    with engine.begin() as conn:
        # Every table, emptied before each test; CASCADE follows the foreign keys.
        conn.execute(
            text(
                "TRUNCATE budgets, default_budgets, expenses, refresh_tokens, "
                "invite_codes, users "
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
def make_user(anon_client: TestClient, db_session: Session) -> Callable[..., User]:
    """Insert a user straight into the DB (no invite needed) and return the row."""

    def _make(email: str = "me@example.com", currency: str = "GBP") -> User:
        user = User(
            email=email, hashed_password=TEST_PASSWORD_HASH, default_currency=currency
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


@pytest.fixture
def client_for(anon_client: TestClient) -> Callable[[User], TestClient]:
    """A separate client that sends this user's access token on every request."""

    def _for(user: User) -> TestClient:
        token = create_access_token(user.id)
        return TestClient(app, headers={"Authorization": f"Bearer {token}"})

    return _for


@pytest.fixture
def client(make_user, client_for) -> TestClient:
    """Logged in as me@example.com (GBP). What most tests use."""
    return client_for(make_user())


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
def make_invite(anon_client: TestClient, db_session: Session) -> Callable[[], str]:
    """Create a fresh, unused invite code and return it."""
    counter = iter(range(1, 1000))

    def _make() -> str:
        code = f"TEST-{next(counter):04d}"
        db_session.add(InviteCode(code=code))
        db_session.commit()
        return code

    return _make
