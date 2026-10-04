from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.web.dependencies import get_exchange_rate_service
from app.interfaces.repositories.sql_exchange_rate_repository import SqlExchangeRateRepository
from app.main import app
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.interfaces.exchange_rate_provider import (
    ExchangeRateProviderInterface,
    ProviderRate,
    SupportedCurrency,
)


class DashboardRateProvider(ExchangeRateProviderInterface):
    name = "dashboard-test"

    def fetch_rate(self, base_currency: str, quote_currency: str, on_date: date) -> ProviderRate:
        return ProviderRate(
            base_currency=base_currency,
            quote_currency=quote_currency,
            requested_date=on_date,
            effective_date=on_date,
            rate=Decimal("5.2500000000"),
            provider=self.name,
        )

    def list_currencies(self) -> list[SupportedCurrency]:
        return []


def _transaction(
    client: TestClient,
    headers: dict[str, str],
    wallet_id: int,
    amount: str,
    transaction_type: str,
    *,
    category_id: int | None = None,
    description: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "category_id": category_id,
            "description": description,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["transaction"]


def test_dashboard_overview_composes_portfolio_widgets(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    budget = client.post(
        "/api/v1/budgets/",
        json={
            "category_id": category["id"],
            "limit_amount": "100.00",
            "alert_threshold": 50,
        },
        headers=auth_headers,
    )
    assert budget.status_code == 201
    goal = client.post(
        "/api/v1/goals/",
        json={"name": "Reserve", "target_amount": "500.00"},
        headers=auth_headers,
    )
    assert goal.status_code == 201

    _transaction(client, auth_headers, wallet["id"], "200.00", "INCOME")
    _transaction(
        client,
        auth_headers,
        wallet["id"],
        "60.00",
        "EXPENSE",
        category_id=category["id"],
    )

    month = datetime.now(UTC).strftime("%Y-%m")
    response = client.get(f"/api/v1/dashboard/overview?month={month}", headers=auth_headers)
    assert response.status_code == 200
    overview = response.json()
    assert overview["month"] == month
    assert overview["currency"] == "BRL"
    assert overview["total_income"] == "200.00"
    assert overview["total_expense"] == "60.00"
    assert overview["net_savings"] == "140.00"
    assert overview["savings_rate"] == "70.00"
    assert overview["transaction_count"] == 2
    assert overview["net_worth"] == "1140.00"
    assert overview["active_wallets"] == 1
    assert overview["active_goals"] == 1
    assert overview["completed_goals"] == 0
    assert overview["budgets_warning"] == 1
    assert overview["budgets_exceeded"] == 0
    assert overview["unread_alerts"] == 1
    assert overview["generated_at"] is not None


def test_dashboard_cash_flow_fills_empty_months(
    client: TestClient, auth_headers: dict[str, str], wallet: dict
):
    _transaction(client, auth_headers, wallet["id"], "300.00", "INCOME")
    _transaction(client, auth_headers, wallet["id"], "75.00", "EXPENSE")

    response = client.get("/api/v1/dashboard/cash-flow?months=3", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["currency"] == "BRL"
    assert len(payload["items"]) == 3
    assert payload["items"][-1] == {
        "month": datetime.now(UTC).strftime("%Y-%m"),
        "income": "300.00",
        "expense": "75.00",
        "net": "225.00",
    }
    assert all(item["income"] == "0.00" for item in payload["items"][:-1])


def test_dashboard_category_breakdown_uses_share_of_all_expenses(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    transport = client.post(
        "/api/v1/categories/",
        json={"name": "Transport"},
        headers=auth_headers,
    ).json()
    _transaction(
        client,
        auth_headers,
        wallet["id"],
        "75.00",
        "EXPENSE",
        category_id=category["id"],
    )
    _transaction(
        client,
        auth_headers,
        wallet["id"],
        "25.00",
        "EXPENSE",
        category_id=transport["id"],
    )

    month = datetime.now(UTC).strftime("%Y-%m")
    response = client.get(
        f"/api/v1/dashboard/spending-by-category?month={month}&limit=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "category_id": category["id"],
            "category_name": "Food",
            "amount": "75.00",
            "percentage": "75.00",
        }
    ]


def test_dashboard_recent_transactions_are_enriched_and_limited(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _transaction(
        client,
        auth_headers,
        wallet["id"],
        "10.00",
        "EXPENSE",
        category_id=category["id"],
        description="Older",
    )
    latest = _transaction(
        client,
        auth_headers,
        wallet["id"],
        "20.00",
        "INCOME",
        description="Latest",
    )
    response = client.get(
        "/api/v1/dashboard/recent-transactions?limit=1", headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    item = response.json()[0]
    assert item["id"] == latest["id"]
    assert item["wallet_name"] == "Main Wallet"
    assert item["category_name"] is None
    assert item["base_amount"] == "20.00"


def test_dashboard_converts_wallet_net_worth_to_base_currency(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
):
    wallet = client.post(
        "/api/v1/wallets/",
        json={"name": "Dollar Account", "currency": "USD", "initial_balance": "10.00"},
        headers=auth_headers,
    )
    assert wallet.status_code == 201
    service = ExchangeRateService(
        SqlExchangeRateRepository(db_session), DashboardRateProvider()
    )
    app.dependency_overrides[get_exchange_rate_service] = lambda: service
    try:
        response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    finally:
        app.dependency_overrides.pop(get_exchange_rate_service, None)
    assert response.status_code == 200
    assert response.json()["net_worth"] == "52.50"


def test_empty_dashboard_and_request_validation(
    client: TestClient, auth_headers: dict[str, str]
):
    overview = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert overview.status_code == 200
    assert overview.json()["total_income"] == "0.00"
    assert overview.json()["net_worth"] == "0.00"
    assert overview.json()["active_wallets"] == 0

    categories = client.get(
        "/api/v1/dashboard/spending-by-category", headers=auth_headers
    )
    assert categories.status_code == 200
    assert categories.json()["items"] == []

    assert (
        client.get("/api/v1/dashboard/overview?month=invalid", headers=auth_headers).status_code
        == 422
    )
    assert (
        client.get("/api/v1/dashboard/cash-flow?months=0", headers=auth_headers).status_code
        == 422
    )
    assert client.get("/api/v1/dashboard/overview").status_code == 401
