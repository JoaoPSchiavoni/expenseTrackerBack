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
                },
                headers=headers,
            )
            assert budget.status_code == 201

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

            archived = client.delete(f"/api/v1/wallets/{wallet.json()['id']}", headers=headers)
            assert archived.status_code == 204
            assert client.get("/health").status_code == 200
    finally:
        with SessionLocal.begin() as session:
            session.execute(delete(UserModel).where(UserModel.email == email))
