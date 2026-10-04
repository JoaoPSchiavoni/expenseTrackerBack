"""
Integration Tests for Authentication Endpoints (Auth).

Why: Validates that register and login endpoints work properly
across the full stack (Router -> Use Case -> Repository -> DB).

Endpoints covered:
1. POST /api/v1/auth/register
2. POST /api/v1/auth/login
"""

from fastapi.testclient import TestClient


class TestAuthRegister:
    """Tests for POST /api/v1/auth/register."""

    def test_register_user_success(self, client: TestClient):
        """Registers a new user and asserts 201 response with correct fields."""
        payload = {
            "email": "newuser@example.com",
            "password": "mypassword123",
            "full_name": "New User",
        }
        res = client.post("/api/v1/auth/register", json=payload)

        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["is_active"] is True
        assert "id" in data
        # Why: Hashed password must never be exposed in API responses
        assert "hashed_password" not in data

    def test_register_duplicate_email_returns_409(self, client: TestClient):
        """Attempting to register an already existing email returns HTTP 409 Conflict."""
        payload = {"email": "dup@example.com", "password": "pass123456"}
        client.post("/api/v1/auth/register", json=payload)

        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 409

    def test_register_invalid_email_returns_422(self, client: TestClient):
        """Invalid email returns HTTP 422 Unprocessable Entity."""
        payload = {"email": "not-an-email", "password": "pass123456"}
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422

    def test_register_short_password_returns_422(self, client: TestClient):
        """Password shorter than 6 characters is rejected by schema validation."""
        payload = {"email": "short@example.com", "password": "12345"}
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422


class TestAuthLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_success(self, client: TestClient):
        """Successful login returns a valid JWT access token."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "securepass",
            },
        )

        res = client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "securepass",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Why: Token string should not be empty
        assert len(data["access_token"]) > 20

    def test_login_wrong_password_returns_401(self, client: TestClient):
        """Incorrect password returns HTTP 401 Unauthorized."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "correctpassword",
            },
        )

        res = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "wrongpassword",
            },
        )
        assert res.status_code == 401

    def test_login_nonexistent_user_returns_401(self, client: TestClient):
        """Non-existent user returns the same HTTP 401 as wrong password.

        Why: Prevents user enumeration by avoiding distinct error messages.
        """
        res = client.post(
            "/api/v1/auth/login",
            json={
                "email": "noexist@example.com",
                "password": "any_password",
            },
        )
        assert res.status_code == 401
