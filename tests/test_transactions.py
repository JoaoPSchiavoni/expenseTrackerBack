from fastapi.testclient import TestClient


def _create_transaction(
    client: TestClient,
    headers: dict,
    wallet_id: int,
    *,
    amount: str,
    transaction_type: str,
    category_id: int | None = None,
):
    payload = {
        "wallet_id": wallet_id,
        "amount": amount,
        "transaction_type": transaction_type,
        "description": "Test transaction",
    }
    if category_id is not None:
        payload["category_id"] = category_id
    return client.post("/api/v1/transactions/", json=payload, headers=headers)


def test_income_and_expense_update_balance(
    client: TestClient, auth_headers: dict, wallet: dict, category: dict
):
    income = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="250.00",
        transaction_type="INCOME",
    )
    assert income.status_code == 201
    assert income.json()["updated_wallet_balance"] == "1250.00"

    expense = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="120.50",
        transaction_type="EXPENSE",
        category_id=category["id"],
    )
    assert expense.status_code == 201
    assert expense.json()["updated_wallet_balance"] == "1129.50"


def test_insufficient_funds_does_not_change_balance(
    client: TestClient, auth_headers: dict, wallet: dict
):
    response = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="1001.00",
        transaction_type="EXPENSE",
    )
    assert response.status_code == 400
    detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert detail.json()["balance"] == "1000.00"


def test_list_and_detail_transactions(client: TestClient, auth_headers: dict, wallet: dict):
    created = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="20.00",
        transaction_type="EXPENSE",
    )
    transaction_id = created.json()["transaction"]["id"]
    listed = client.get(f"/api/v1/transactions/?wallet_id={wallet['id']}", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    detail = client.get(f"/api/v1/transactions/{transaction_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["amount"] == "20.00"


def test_update_transaction_recalculates_balance(
    client: TestClient, auth_headers: dict, wallet: dict
):
    created = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="100.00",
        transaction_type="EXPENSE",
    ).json()
    transaction_id = created["transaction"]["id"]

    updated = client.put(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "50.00", "transaction_type": "INCOME", "description": "Correction"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["updated_wallet_balance"] == "1050.00"
    assert updated.json()["transaction"]["transaction_type"] == "INCOME"


def test_delete_transaction_reverses_balance(client: TestClient, auth_headers: dict, wallet: dict):
    created = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="75.00",
        transaction_type="EXPENSE",
    ).json()
    transaction_id = created["transaction"]["id"]
    response = client.delete(f"/api/v1/transactions/{transaction_id}", headers=auth_headers)
    assert response.status_code == 204
    wallet_response = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert wallet_response.json()["balance"] == "1000.00"


def test_bulk_creation_is_processed(client: TestClient, auth_headers: dict, wallet: dict):
    response = client.post(
        "/api/v1/transactions/bulk",
        json={
            "transactions": [
                {"wallet_id": wallet["id"], "amount": "10.00", "transaction_type": "INCOME"},
                {"wallet_id": wallet["id"], "amount": "5.00", "transaction_type": "EXPENSE"},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["processed"] == 2
    detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert detail.json()["balance"] == "1005.00"


def test_bulk_creation_rolls_back_every_item_on_failure(
    client: TestClient, auth_headers: dict, wallet: dict
):
    response = client.post(
        "/api/v1/transactions/bulk",
        json={
            "transactions": [
                {"wallet_id": wallet["id"], "amount": "100.00", "transaction_type": "INCOME"},
                {
                    "wallet_id": wallet["id"],
                    "amount": "2000.00",
                    "transaction_type": "EXPENSE",
                },
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert detail.json()["balance"] == "1000.00"
    listed = client.get(f"/api/v1/transactions/?wallet_id={wallet['id']}", headers=auth_headers)
    assert listed.json() == []


def test_nonexistent_wallet_and_category_return_404(
    client: TestClient, auth_headers: dict, wallet: dict
):
    assert (
        _create_transaction(
            client,
            auth_headers,
            99999,
            amount="10.00",
            transaction_type="INCOME",
        ).status_code
        == 404
    )
    response = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="10.00",
        transaction_type="EXPENSE",
        category_id=99999,
    )
    assert response.status_code == 404


def test_transaction_is_not_visible_to_another_user(
    client: TestClient, auth_headers: dict, wallet: dict
):
    created = _create_transaction(
        client,
        auth_headers,
        wallet["id"],
        amount="10.00",
        transaction_type="INCOME",
    ).json()
    transaction_id = created["transaction"]["id"]

    client.post(
        "/api/v1/auth/register",
        json={"email": "transaction-other@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "transaction-other@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/transactions/{transaction_id}", headers=headers).status_code == 404
    forbidden_create = _create_transaction(
        client,
        headers,
        wallet["id"],
        amount="10.00",
        transaction_type="INCOME",
    )
    assert forbidden_create.status_code == 403
