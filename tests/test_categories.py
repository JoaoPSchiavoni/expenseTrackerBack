from fastapi.testclient import TestClient


def test_category_crud(client: TestClient, auth_headers: dict):
    assert client.get("/api/v1/categories/", headers=auth_headers).json() == []

    created = client.post(
        "/api/v1/categories/",
        json={"name": "Food", "description": "Meals"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    listed = client.get("/api/v1/categories/", headers=auth_headers)
    assert [item["name"] for item in listed.json()] == ["Food"]

    detail = client.get(f"/api/v1/categories/{category_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["description"] == "Meals"

    updated = client.put(
        f"/api/v1/categories/{category_id}",
        json={"name": "Dining", "description": "Restaurants"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Dining"

    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/categories/{category_id}", headers=auth_headers).status_code == 404


def test_duplicate_category_returns_409(client: TestClient, auth_headers: dict, category: dict):
    response = client.post("/api/v1/categories/", json={"name": "food"}, headers=auth_headers)
    assert response.status_code == 409


def test_category_requires_authentication(client: TestClient):
    assert client.post("/api/v1/categories/", json={"name": "Test"}).status_code == 401


def test_category_is_not_visible_to_another_user(
    client: TestClient, auth_headers: dict, category: dict
):
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(f"/api/v1/categories/{category['id']}", headers=other_headers)
    assert response.status_code == 404
