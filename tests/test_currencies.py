from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ExchangeRateModel


def _cache_rate(
    session: Session,
    *,
    base: str,
    quote: str,
    requested_date: date,
    effective_date: date,
    rate: str,
) -> None:
    session.add(
        ExchangeRateModel(
            base_currency=base,
            quote_currency=quote,
            requested_date=requested_date,
            effective_date=effective_date,
            rate=Decimal(rate),
            provider="frankfurter",
        )
    )
    session.flush()


def test_identity_quote_does_not_need_external_provider(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.get(
        "/api/v1/currencies/quote",
        params={
            "amount": "12.50",
            "base_currency": "brl",
            "quote_currency": "BRL",
            "date": "2026-09-30",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "base_currency": "BRL",
        "quote_currency": "BRL",
        "amount": "12.50",
        "converted_amount": "12.50",
        "rate": "1.0000000000",
        "requested_date": "2026-09-30",
        "effective_date": "2026-09-30",
        "provider": "identity",
    }


def test_cached_quote_is_used_without_network(
    client: TestClient, auth_headers: dict, db_session: Session
) -> None:
    _cache_rate(
        db_session,
        base="USD",
        quote="BRL",
        requested_date=date(2026, 9, 30),
        effective_date=date(2026, 9, 30),
        rate="5.2027",
    )
    response = client.get(
        "/api/v1/currencies/quote",
        params={
            "amount": "10.00",
            "base_currency": "USD",
            "quote_currency": "BRL",
            "date": "2026-09-30",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["converted_amount"] == "52.03"
    assert response.json()["rate"] == "5.2027000000"


def test_multicurrency_transaction_stores_conversion_snapshot_and_report_value(
    client: TestClient, auth_headers: dict, db_session: Session
) -> None:
    wallet = client.post(
        "/api/v1/wallets/",
        json={"name": "USD account", "currency": "USD", "initial_balance": "100.00"},
        headers=auth_headers,
    ).json()
    _cache_rate(
        db_session,
        base="USD",
        quote="BRL",
        requested_date=date(2026, 9, 30),
        effective_date=date(2026, 9, 30),
        rate="5.2027",
    )

    response = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "10.00",
            "transaction_type": "EXPENSE",
            "occurred_at": "2026-09-30T12:00:00-03:00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    transaction = response.json()["transaction"]
    assert transaction["currency"] == "USD"
    assert transaction["base_currency"] == "BRL"
    assert transaction["exchange_rate"] == "5.2027000000"
    assert transaction["base_amount"] == "52.03"
    assert transaction["source"] == "MANUAL"

    report = client.get("/api/v1/reports/monthly?month=2026-09", headers=auth_headers)
    assert report.status_code == 200
    assert report.json()["total_expense"] == "52.03"
    assert report.json()["currency"] == "BRL"


def test_transaction_date_change_refreshes_historical_rate(
    client: TestClient, auth_headers: dict, db_session: Session
) -> None:
    wallet = client.post(
        "/api/v1/wallets/",
        json={"name": "USD account", "currency": "USD", "initial_balance": "100.00"},
        headers=auth_headers,
    ).json()
    for day, rate in ((date(2026, 9, 29), "5.00"), (date(2026, 9, 30), "5.20")):
        _cache_rate(
            db_session,
            base="USD",
            quote="BRL",
            requested_date=day,
            effective_date=day,
            rate=rate,
        )
    created = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "10.00",
            "transaction_type": "EXPENSE",
            "occurred_at": "2026-09-29T12:00:00-03:00",
        },
        headers=auth_headers,
    ).json()
    updated = client.put(
        f"/api/v1/transactions/{created['transaction']['id']}",
        json={"occurred_at": "2026-09-30T12:00:00-03:00"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["transaction"]["base_amount"] == "52.00"


def test_currency_inputs_use_three_letter_codes(client: TestClient, auth_headers: dict) -> None:
    wallet = client.post(
        "/api/v1/wallets/",
        json={"name": "Invalid", "currency": "REAL"},
        headers=auth_headers,
    )
    assert wallet.status_code == 422
