"""Opt-in end-to-end validation against the configured PostgreSQL database."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import UserModel
from app.main import app

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="Set RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests",
    ),
]


def test_complete_financial_flow_on_postgres() -> None:
    email = f"postgres-smoke-{uuid4().hex}@example.com"
    headers: dict[str, str] = {}

    try:
        with TestClient(app) as client:
            registered = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "postgres-test-password"},
            )
            assert registered.status_code == 201

            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "postgres-test-password"},
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            category = client.post(
                "/api/v1/categories/",
                json={"name": "Integration", "description": "PostgreSQL validation"},
                headers=headers,
            )
            assert category.status_code == 201

            wallet = client.post(
                "/api/v1/wallets/",
                json={"name": "Integration Wallet", "initial_balance": "100.00"},
                headers=headers,
            )
            assert wallet.status_code == 201

            budget = client.post(
                "/api/v1/budgets/",
                json={
                    "category_id": category.json()["id"],
                    "limit_amount": "75.00",
                    "period": "MONTHLY",
                    "alert_threshold": 20,
                },
                headers=headers,
            )
            assert budget.status_code == 201

            goal = client.post(
                "/api/v1/goals/",
                json={"name": "Integration Goal", "target_amount": "100.00"},
                headers=headers,
            )
            assert goal.status_code == 201
            contribution = client.post(
                f"/api/v1/goals/{goal.json()['id']}/contributions",
                json={"amount": "25.00", "note": "PostgreSQL validation"},
                headers=headers,
            )
            assert contribution.status_code == 201
            assert contribution.json()["goal"]["current_amount"] == "25.00"
            assert contribution.json()["goal"]["progress_percentage"] == "25.00"

            transaction = client.post(
                "/api/v1/transactions/",
                json={
                    "wallet_id": wallet.json()["id"],
                    "category_id": category.json()["id"],
                    "amount": "25.00",
                    "transaction_type": "EXPENSE",
                },
                headers=headers,
            )
            assert transaction.status_code == 201
            assert transaction.json()["updated_wallet_balance"] == "75.00"

            alerts = client.get("/api/v1/budget-alerts/", headers=headers)
            assert alerts.status_code == 200
            assert len(alerts.json()) == 1
            assert alerts.json()[0]["alert_type"] == "WARNING"
            assert alerts.json()[0]["spent_amount"] == "25.00"

            transaction_id = transaction.json()["transaction"]["id"]
            updated = client.put(
                f"/api/v1/transactions/{transaction_id}",
                json={"amount": "20.00"},
                headers=headers,
            )
            assert updated.status_code == 200
            assert updated.json()["updated_wallet_balance"] == "80.00"

            month = datetime.now(UTC).strftime("%Y-%m")
            report = client.get(f"/api/v1/reports/monthly?month={month}", headers=headers)
            assert report.status_code == 200
            assert report.json()["total_expense"] == "20.00"

            deleted = client.delete(f"/api/v1/transactions/{transaction_id}", headers=headers)
            assert deleted.status_code == 204

            statement = b"Data;Descricao;Valor;ID\n04/10/2026;Imported income;5,00;pg-1\n"
            preview = client.post(
                "/api/v1/imports/",
                data={"wallet_id": str(wallet.json()["id"])},
                files={"file": ("postgres.csv", statement, "text/csv")},
                headers=headers,
            )
            assert preview.status_code == 201
            confirmed = client.post(
                f"/api/v1/imports/{preview.json()['batch']['id']}/confirm",
                json={},
                headers=headers,
            )
            assert confirmed.status_code == 200
            assert confirmed.json()["batch"]["imported_rows"] == 1

            archived = client.delete(f"/api/v1/wallets/{wallet.json()['id']}", headers=headers)
            assert archived.status_code == 204
            assert client.get("/health").status_code == 200
    finally:
        with SessionLocal.begin() as session:
            session.execute(delete(UserModel).where(UserModel.email == email))
