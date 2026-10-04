from fastapi.testclient import TestClient


def test_get_profile(client: TestClient, auth_headers: dict):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "testuser@example.com"
    assert "hashed_password" not in response.json()
    assert response.json()["base_currency"] == "BRL"
    assert response.json()["timezone"] == "America/Sao_Paulo"


def test_update_profile_is_persisted(client: TestClient, auth_headers: dict):
    response = client.put(
        "/api/v1/users/me",
        json={"full_name": "Updated Name", "email": "updated@example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert response.json()["email"] == "updated@example.com"

    profile = client.get("/api/v1/users/me", headers=auth_headers)
    assert profile.json()["email"] == "updated@example.com"


def test_change_password(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "securepassword123", "new_password": "newpassword456"},
        headers=auth_headers,
    )
    assert response.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "testuser@example.com", "password": "securepassword123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "testuser@example.com", "password": "newpassword456"},
        ).status_code
        == 200
    )


def test_change_password_rejects_wrong_current_password(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_delete_deactivates_account(client: TestClient, auth_headers: dict):
    response = client.delete("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 204
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "securepassword123"},
    )
    assert login.status_code == 401


def test_profile_requires_authentication(client: TestClient):
    assert client.get("/api/v1/users/me").status_code == 401
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer invalid.token.here"}
        ).status_code
        == 401
    )


def test_update_financial_preferences_before_first_transaction(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"base_currency": "usd", "timezone": "Europe/Lisbon"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["base_currency"] == "USD"
    assert response.json()["timezone"] == "Europe/Lisbon"


def test_base_currency_is_locked_after_first_transaction(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    created = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "10.00",
            "transaction_type": "EXPENSE",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"base_currency": "USD"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_preferences_validate_timezone(client: TestClient, auth_headers: dict) -> None:
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"timezone": "Mars/Olympus"},
        headers=auth_headers,
    )
    assert response.status_code == 422
