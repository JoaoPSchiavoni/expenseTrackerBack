from datetime import datetime

from fastapi.testclient import TestClient


def test_demo_session_is_seeded_and_isolated(client: TestClient) -> None:
    first = client.post("/api/v1/auth/demo-session")
    second = client.post("/api/v1/auth/demo-session")
    assert first.status_code == second.status_code == 200
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    first_user = client.get("/api/v1/users/me", headers=first_headers).json()
    second_user = client.get("/api/v1/users/me", headers=second_headers).json()
    assert first_user["is_demo"] is True
    assert first_user["onboarding_completed"] is True
    assert first_user["id"] != second_user["id"]
    assert len(client.get("/api/v1/wallets/", headers=first_headers).json()) == 2
    assert len(client.get("/api/v1/categories/", headers=first_headers).json()) == 7
    assert len(client.get("/api/v1/goals/", headers=first_headers).json()) == 1
    assert len(client.get("/api/v1/automation/rules", headers=first_headers).json()) == 2


def test_monthly_pdf_has_downloadable_pdf(
    client: TestClient, auth_headers: dict, wallet: dict
) -> None:
    now = datetime.now()
    created = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "100.00",
            "transaction_type": "INCOME",
            "description": "Receita do mês",
            "occurred_at": now.isoformat(),
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    response = client.get(
        f"/api/v1/reports/monthly.pdf?month={now:%Y-%m}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_onboarding_preference_can_be_completed(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"onboarding_completed": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is True
