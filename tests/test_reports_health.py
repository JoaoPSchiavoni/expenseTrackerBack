from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_reports_use_persisted_transactions(
    client: TestClient, auth_headers: dict, wallet: dict, category: dict
):
    month = datetime.now(UTC).strftime("%Y-%m")
    for transaction in (
        {"amount": "500.00", "transaction_type": "INCOME"},
        {
            "amount": "125.50",
            "transaction_type": "EXPENSE",
            "category_id": category["id"],
        },
    ):
        response = client.post(
            "/api/v1/transactions/",
            json={"wallet_id": wallet["id"], **transaction},
            headers=auth_headers,
        )
        assert response.status_code == 201

    monthly = client.get(f"/api/v1/reports/monthly?month={month}", headers=auth_headers)
    assert monthly.status_code == 200
    assert monthly.json() == {
        "month": month,
        "currency": "BRL",
        "total_income": "500.00",
        "total_expense": "125.50",
        "net_savings": "374.50",
    }

    summary = client.get(f"/api/v1/reports/category-summary?period={month}", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["items"] == [
        {"category_id": category["id"], "category_name": "Food", "total_spent": "125.50"}
    ]


def test_empty_month_returns_zero_totals(client: TestClient, auth_headers: dict):
    response = client.get("/api/v1/reports/monthly?month=2000-01", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["net_savings"] == "0.00"


def test_reports_validate_period_and_authentication(client: TestClient, auth_headers: dict):
    assert (
        client.get("/api/v1/reports/monthly?month=invalid", headers=auth_headers).status_code == 422
    )
    assert client.get("/api/v1/reports/monthly?month=2026-10").status_code == 401


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
