from fastapi.testclient import TestClient


def test_create_and_list_wallets(client: TestClient, auth_headers: dict):
    assert client.get("/api/v1/wallets/", headers=auth_headers).json() == []
    response = client.post(
        "/api/v1/wallets/",
        json={"name": "Checking", "currency": "brl", "initial_balance": "1000.00"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["balance"] == "1000.00"
    assert data["is_active"] is True

    listed = client.get("/api/v1/wallets/", headers=auth_headers)
    assert len(listed.json()) == 1


def test_default_balance_is_zero(client: TestClient, auth_headers: dict):
    response = client.post("/api/v1/wallets/", json={"name": "Cash"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["balance"] == "0.00"


def test_wallet_detail_and_update(client: TestClient, auth_headers: dict, wallet: dict):
    detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["name"] == "Main Wallet"

    updated = client.put(
        f"/api/v1/wallets/{wallet['id']}",
        json={"name": "Primary", "currency": "usd"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Primary"
    assert updated.json()["currency"] == "USD"
    assert updated.json()["balance"] == "1000.00"


def test_delete_archives_wallet(client: TestClient, auth_headers: dict, wallet: dict):
    response = client.delete(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/wallets/", headers=auth_headers).json() == []


def test_wallet_not_found(client: TestClient, auth_headers: dict):
    assert client.get("/api/v1/wallets/99999", headers=auth_headers).status_code == 404
    assert client.delete("/api/v1/wallets/99999", headers=auth_headers).status_code == 404


def test_wallet_requires_authentication(client: TestClient):
    assert client.post("/api/v1/wallets/", json={"name": "Private"}).status_code == 401


def test_wallet_currency_is_locked_after_first_transaction(
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
    response = client.put(
        f"/api/v1/wallets/{wallet['id']}",
        json={"currency": "USD"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_wallet_is_not_visible_to_another_user(
    client: TestClient, auth_headers: dict, wallet: dict
):
    client.post(
        "/api/v1/auth/register",
        json={"email": "wallet-other@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "wallet-other@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/wallets/{wallet['id']}", headers=headers).status_code == 404
