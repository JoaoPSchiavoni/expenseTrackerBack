from fastapi.testclient import TestClient


def _create_schedule(
    client: TestClient,
    headers: dict[str, str],
    wallet_id: int,
    **overrides: object,
) -> dict:
    payload: dict[str, object] = {
        "wallet_id": wallet_id,
        "amount": "100.00",
        "transaction_type": "EXPENSE",
        "description": "Assinatura mensal",
        "frequency": "MONTHLY",
        "interval_count": 1,
        "start_date": "2026-01-31",
    }
    payload.update(overrides)
    response = client.post("/api/v1/recurring-transactions/", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_update_and_delete_recurring_transaction(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
) -> None:
    created = _create_schedule(client, auth_headers, wallet["id"])

    assert created["category_id"] is None
    assert created["next_run_date"] == "2026-01-31"
    assert created["is_active"] is True

    listed = client.get("/api/v1/recurring-transactions/", headers=auth_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    updated = client.put(
        f"/api/v1/recurring-transactions/{created['id']}",
        json={"amount": "125.50", "is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == "125.50"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/recurring-transactions/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/v1/recurring-transactions/{created['id']}", headers=auth_headers
        ).status_code
        == 404
    )


def test_process_due_materializes_month_end_occurrences_once(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
) -> None:
    recurring = _create_schedule(client, auth_headers, wallet["id"])

    processed = client.post(
        "/api/v1/recurring-transactions/process-due?through_date=2026-03-31",
        headers=auth_headers,
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["generated"] == 3

    transactions = client.get(
        f"/api/v1/transactions/?wallet_id={wallet['id']}", headers=auth_headers
    )
    assert transactions.status_code == 200
    assert {item["occurred_at"][:10] for item in transactions.json()} == {
        "2026-01-31",
        "2026-02-28",
        "2026-03-31",
    }
    assert {item["source"] for item in transactions.json()} == {"RECURRING"}

    wallet_detail = client.get(f"/api/v1/wallets/{wallet['id']}", headers=auth_headers)
    assert wallet_detail.json()["balance"] == "700.00"

    schedule = client.get(f"/api/v1/recurring-transactions/{recurring['id']}", headers=auth_headers)
    assert schedule.json()["next_run_date"] == "2026-04-30"

    repeated = client.post(
        "/api/v1/recurring-transactions/process-due?through_date=2026-03-31",
        headers=auth_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["generated"] == 0


def test_recurring_transaction_validates_wallet_and_date_range(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
) -> None:
    invalid_period = client.post(
        "/api/v1/recurring-transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "25.00",
            "transaction_type": "INCOME",
            "frequency": "WEEKLY",
            "start_date": "2026-10-10",
            "end_date": "2026-10-09",
        },
        headers=auth_headers,
    )
    assert invalid_period.status_code == 422

    missing_wallet = client.post(
        "/api/v1/recurring-transactions/",
        json={
            "wallet_id": 99999,
            "amount": "25.00",
            "transaction_type": "INCOME",
            "frequency": "WEEKLY",
            "start_date": "2026-10-10",
        },
        headers=auth_headers,
    )
    assert missing_wallet.status_code == 404
