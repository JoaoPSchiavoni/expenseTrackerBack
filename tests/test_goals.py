from datetime import date, timedelta

from fastapi.testclient import TestClient


def _create_goal(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Emergency fund",
    target_amount: str = "1000.00",
) -> dict:
    response = client.post(
        "/api/v1/goals/",
        json={
            "name": name,
            "description": "Six months of essential expenses",
            "target_amount": target_amount,
            "target_date": (date.today() + timedelta(days=365)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _other_user_headers(client: TestClient) -> dict[str, str]:
    payload = {
        "email": "other-goals@example.com",
        "password": "securepassword123",
        "full_name": "Other User",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_goal_crud_and_computed_progress(client: TestClient, auth_headers: dict[str, str]):
    goal = _create_goal(client, auth_headers)
    assert goal["currency"] == "BRL"
    assert goal["current_amount"] == "0.00"
    assert goal["remaining_amount"] == "1000.00"
    assert goal["progress_percentage"] == "0.00"
    assert goal["status"] == "ACTIVE"

    listed = client.get("/api/v1/goals/", headers=auth_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [goal["id"]]

    detail = client.get(f"/api/v1/goals/{goal['id']}", headers=auth_headers)
    assert detail.status_code == 200

    updated = client.put(
        f"/api/v1/goals/{goal['id']}",
        json={"name": "  Safety net  ", "description": None, "target_amount": "1200.00"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Safety net"
    assert updated.json()["description"] is None
    assert updated.json()["target_amount"] == "1200.00"

    deleted = client.delete(f"/api/v1/goals/{goal['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/goals/{goal['id']}", headers=auth_headers).status_code == 404


def test_contributions_complete_goal_and_preserve_history(
    client: TestClient, auth_headers: dict[str, str]
):
    goal = _create_goal(client, auth_headers, target_amount="300.00")
    first = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={
            "amount": "75.00",
            "note": "First deposit",
            "contributed_at": "2026-10-04T09:30:00",
        },
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert first.json()["goal"]["current_amount"] == "75.00"
    assert first.json()["goal"]["remaining_amount"] == "225.00"
    assert first.json()["goal"]["progress_percentage"] == "25.00"
    assert first.json()["contribution"]["contributed_at"].startswith("2026-10-04T12:30:00")

    completed = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "225.00", "note": "Finish"},
        headers=auth_headers,
    )
    assert completed.status_code == 201
    completed_goal = completed.json()["goal"]
    assert completed_goal["status"] == "COMPLETED"
    assert completed_goal["progress_percentage"] == "100.00"
    assert completed_goal["completed_at"] is not None

    history = client.get(f"/api/v1/goals/{goal['id']}/contributions", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert {item["note"] for item in history.json()} == {"First deposit", "Finish"}


def test_contribution_guards_and_target_invariants(
    client: TestClient, auth_headers: dict[str, str]
):
    goal = _create_goal(client, auth_headers, target_amount="100.00")
    too_large = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "100.01"},
        headers=auth_headers,
    )
    assert too_large.status_code == 409
    assert too_large.json()["error"] == "INVALID_GOAL_STATE"

    assert (
        client.post(
            f"/api/v1/goals/{goal['id']}/contributions",
            json={"amount": "60.00"},
            headers=auth_headers,
        ).status_code
        == 201
    )
    below_saved = client.put(
        f"/api/v1/goals/{goal['id']}",
        json={"target_amount": "59.99"},
        headers=auth_headers,
    )
    assert below_saved.status_code == 409

    completed = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "40.00"},
        headers=auth_headers,
    )
    assert completed.status_code == 201
    blocked = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "1.00"},
        headers=auth_headers,
    )
    assert blocked.status_code == 409


def test_removing_contribution_reopens_completed_goal(
    client: TestClient, auth_headers: dict[str, str]
):
    goal = _create_goal(client, auth_headers, target_amount="50.00")
    added = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "50.00"},
        headers=auth_headers,
    ).json()
    contribution_id = added["contribution"]["id"]

    removed = client.delete(
        f"/api/v1/goals/{goal['id']}/contributions/{contribution_id}",
        headers=auth_headers,
    )
    assert removed.status_code == 200
    assert removed.json()["current_amount"] == "0.00"
    assert removed.json()["status"] == "ACTIVE"
    assert removed.json()["completed_at"] is None
    assert (
        client.delete(
            f"/api/v1/goals/{goal['id']}/contributions/{contribution_id}",
            headers=auth_headers,
        ).status_code
        == 404
    )


def test_cancel_reopen_and_filter_goals(client: TestClient, auth_headers: dict[str, str]):
    cancelled_goal = _create_goal(client, auth_headers, name="Cancelled")
    _create_goal(client, auth_headers, name="Active")

    cancelled = client.put(
        f"/api/v1/goals/{cancelled_goal['id']}",
        json={"status": "CANCELLED"},
        headers=auth_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (
        client.post(
            f"/api/v1/goals/{cancelled_goal['id']}/contributions",
            json={"amount": "10.00"},
            headers=auth_headers,
        ).status_code
        == 409
    )

    filtered = client.get("/api/v1/goals/?status=CANCELLED", headers=auth_headers)
    assert filtered.status_code == 200
    assert [item["name"] for item in filtered.json()] == ["Cancelled"]

    reopened = client.put(
        f"/api/v1/goals/{cancelled_goal['id']}",
        json={"status": "ACTIVE"},
        headers=auth_headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "ACTIVE"


def test_increasing_completed_target_reopens_goal(client: TestClient, auth_headers: dict[str, str]):
    goal = _create_goal(client, auth_headers, target_amount="100.00")
    client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"amount": "100.00"},
        headers=auth_headers,
    )
    updated = client.put(
        f"/api/v1/goals/{goal['id']}",
        json={"target_amount": "150.00", "status": "ACTIVE"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "ACTIVE"
    assert updated.json()["remaining_amount"] == "50.00"


def test_goal_ownership_is_enforced(client: TestClient, auth_headers: dict[str, str]):
    goal = _create_goal(client, auth_headers)
    other_headers = _other_user_headers(client)
    endpoints = [
        ("get", f"/api/v1/goals/{goal['id']}"),
        ("put", f"/api/v1/goals/{goal['id']}"),
        ("delete", f"/api/v1/goals/{goal['id']}"),
        ("get", f"/api/v1/goals/{goal['id']}/contributions"),
        ("post", f"/api/v1/goals/{goal['id']}/contributions"),
    ]
    for method, url in endpoints:
        kwargs = {"headers": other_headers}
        if method == "put":
            kwargs["json"] = {"name": "Stolen"}
        elif method == "post":
            kwargs["json"] = {"amount": "10.00"}
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 404


def test_goal_validation_and_authentication(client: TestClient, auth_headers: dict[str, str]):
    invalid_payloads = [
        {"name": "", "target_amount": "100.00"},
        {"name": "Trip", "target_amount": "0.00"},
        {"name": "Trip", "target_amount": "1.001"},
    ]
    for payload in invalid_payloads:
        assert client.post("/api/v1/goals/", json=payload, headers=auth_headers).status_code == 422
    assert (
        client.post("/api/v1/goals/", json={"name": "Trip", "target_amount": "100.00"}).status_code
        == 401
    )
