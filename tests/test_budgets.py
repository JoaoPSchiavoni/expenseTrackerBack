from fastapi.testclient import TestClient


def test_budget_crud(client: TestClient, auth_headers: dict, category: dict):
    created = client.post(
        "/api/v1/budgets/",
        json={"category_id": category["id"], "limit_amount": "500.00", "period": "MONTHLY"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["limit_amount"] == "500.00"
    budget_id = created.json()["id"]

    listed = client.get("/api/v1/budgets/", headers=auth_headers)
    assert len(listed.json()) == 1

    detail = client.get(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
    assert detail.status_code == 200

    updated = client.put(
        f"/api/v1/budgets/{budget_id}",
        json={"limit_amount": "750.00", "period": "WEEKLY"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["limit_amount"] == "750.00"
    assert updated.json()["period"] == "WEEKLY"

    deleted = client.delete(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/budgets/{budget_id}", headers=auth_headers).status_code == 404


def test_budget_requires_owned_category(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/v1/budgets/",
        json={"category_id": 999, "limit_amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_duplicate_budget_scope_returns_409(client: TestClient, auth_headers: dict, category: dict):
    payload = {"category_id": category["id"], "limit_amount": "100.00", "period": "MONTHLY"}
    assert client.post("/api/v1/budgets/", json=payload, headers=auth_headers).status_code == 201
    assert client.post("/api/v1/budgets/", json=payload, headers=auth_headers).status_code == 409


def test_budget_validation_and_authentication(client: TestClient, auth_headers: dict):
    assert (
        client.post(
            "/api/v1/budgets/",
            json={"category_id": 1, "limit_amount": "-1.00"},
            headers=auth_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/budgets/", json={"category_id": 1, "limit_amount": "100.00"}
        ).status_code
        == 401
    )
