from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_rule_crud_matching_and_import_application(
    client: TestClient, auth_headers: dict, wallet: dict, category: dict
) -> None:
    created = client.post(
        "/api/v1/automation/rules",
        json={
            "category_id": category["id"],
            "name": "Mercados",
            "pattern": "mercado",
            "match_type": "CONTAINS",
            "priority": 10,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    rule = created.json()
    assert rule["category_id"] == category["id"]

    matched = client.post(
        "/api/v1/automation/rules/test-match",
        json={"description": "Mercado do bairro"},
        headers=auth_headers,
    )
    assert matched.json() == {"category_id": category["id"], "matched": True}

    automatic = client.post(
        "/api/v1/transactions/",
        json={
            "wallet_id": wallet["id"],
            "amount": "10.00",
            "transaction_type": "EXPENSE",
            "description": "Mercado do bairro",
        },
        headers=auth_headers,
    )
    assert automatic.status_code == 201
    assert automatic.json()["transaction"]["category_id"] == category["id"]

    statement = "Data;Descrição;Valor;Tipo;ID\n03/10/2026;Mercado Central;125,50;despesa;x-1\n"
    preview = client.post(
        "/api/v1/imports/",
        data={"wallet_id": str(wallet["id"])},
        files={"file": ("statement.csv", statement.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert preview.status_code == 201
    assert preview.json()["items"][0]["category_id"] == category["id"]

    updated = client.put(
        f"/api/v1/automation/rules/{rule['id']}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    deleted = client.delete(
        f"/api/v1/automation/rules/{rule['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204


def test_subscription_detection_and_billing_alerts(
    client: TestClient, auth_headers: dict, wallet: dict, category: dict
) -> None:
    today = datetime.now(UTC).date()
    for days_ago, amount in ((91, "54.90"), (61, "55.90"), (31, "56.90")):
        response = client.post(
            "/api/v1/transactions/",
            json={
                "wallet_id": wallet["id"],
                "category_id": category["id"],
                "amount": amount,
                "transaction_type": "EXPENSE",
                "description": "Netflix 1234",
                "occurred_at": datetime.combine(
                    today - timedelta(days=days_ago), datetime.min.time(), tzinfo=UTC
                ).isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    detected = client.post(
        "/api/v1/automation/subscriptions/detect", headers=auth_headers
    )
    assert detected.status_code == 200
    assert detected.json()["detected"] == 1
    subscription = detected.json()["subscriptions"][0]
    assert subscription["frequency"] == "MONTHLY"
    assert DecimalText(subscription["average_amount"]) == "55.90"

    synced = client.post(
        "/api/v1/automation/billing-alerts/sync?days_ahead=7", headers=auth_headers
    )
    assert synced.status_code == 200
    assert synced.json()["generated"] == 1
    alert = synced.json()["alerts"][0]
    assert alert["alert_type"] == "OVERDUE"

    read = client.patch(
        f"/api/v1/automation/billing-alerts/{alert['id']}/read", headers=auth_headers
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None

    dismissed = client.patch(
        f"/api/v1/automation/subscriptions/{subscription['id']}",
        json={"status": "DISMISSED"},
        headers=auth_headers,
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "DISMISSED"


def DecimalText(value: str) -> str:
    return f"{float(value):.2f}"


def test_invalid_regex_is_rejected(
    client: TestClient, auth_headers: dict, category: dict
) -> None:
    response = client.post(
        "/api/v1/automation/rules",
        json={
            "category_id": category["id"],
            "name": "Regex inválida",
            "pattern": "([",
            "match_type": "REGEX",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
