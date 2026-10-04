"""
Pytest Test Fixtures and Test Database Configuration.

Why: Configures an in-memory SQLite database (isolated per test function)
and overrides FastAPI's get_db dependency, allowing fast, reproducible
integration tests without requiring a live external PostgreSQL instance.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.connection import Base
from app.infrastructure.web.dependencies import get_db
from app.main import app

# In-memory SQLite configuration with StaticPool to share state across test connection
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test,
)


@pytest.fixture(scope="function")
def db_session():
    """Creates a clean database schema for each test function.

    Why: Guarantees complete isolation between tests, avoiding side effects.
    """
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client(db_session):
    """HTTP test client (TestClient) with test session dependency injection.

    Why: Replaces application get_db dependency with isolated in-memory test session.
    """

    def override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client):
    """Helper fixture that registers a user, logs in, and returns JWT Bearer authorization headers.

    Why: Automates the setup authentication flow so business logic tests
    focus strictly on wallets and transactions.
    """
    user_payload = {
        "email": "testuser@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }
    # 1. Register
    reg_response = client.post("/api/v1/auth/register", json=user_payload)
    assert reg_response.status_code == 201

    # 2. Login
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def wallet(client, auth_headers):
    response = client.post(
        "/api/v1/wallets/",
        json={"name": "Main Wallet", "currency": "BRL", "initial_balance": "1000.00"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(scope="function")
def category(client, auth_headers):
    response = client.post(
        "/api/v1/categories/",
        json={"name": "Food", "description": "Meals and groceries"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()
