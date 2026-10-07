from datetime import date, timedelta

from fastapi.testclient import TestClient


def _create_budget(
    client: TestClient,
    headers: dict[str, str],
    category_id: int,
    *,
    limit: str = "100.00",
    threshold: int = 80,
    period: str = "MONTHLY",
    enabled: bool = True,
) -> dict:
    response = client.post(
        "/api/v1/budgets/",
        json={
            "category_id": category_id,
            "limit_amount": limit,
            "period": period,
            "alert_threshold": threshold,
            "alerts_enabled": enabled,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _expense(
    client: TestClient,
    headers: dict[str, str],
    wallet_id: int,
    category_id: int | None,
    amount: str,
    *,
    occurred_at: str | None = None,
) -> dict:
    payload = {
        "wallet_id": wallet_id,
        "category_id": category_id,
        "amount": amount,
        "transaction_type": "EXPENSE",
    }
    if occurred_at is not None:
        payload["occurred_at"] = occurred_at
    response = client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()["transaction"]


def _alerts(
    client: TestClient,
    headers: dict[str, str],
    *,
    active_only: bool = True,
) -> list[dict]:
    response = client.get(
        f"/api/v1/budget-alerts/?active_only={str(active_only).lower()}",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _other_user_headers(client: TestClient) -> dict[str, str]:
    credentials = {"email": "budget-alert-other@example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_warning_and_exceeded_alerts_are_generated_and_deduplicated(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    budget = _create_budget(client, auth_headers, category["id"])
    assert budget["alert_threshold"] == 80
    assert budget["alerts_enabled"] is True

    _expense(client, auth_headers, wallet["id"], category["id"], "79.00")
    assert _alerts(client, auth_headers) == []

    status = client.get(f"/api/v1/budgets/{budget['id']}/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["spent_amount"] == "79.00"
    assert status.json()["status"] == "SAFE"

    _expense(client, auth_headers, wallet["id"], category["id"], "1.00")
    warning = _alerts(client, auth_headers)
    assert len(warning) == 1
    assert warning[0]["alert_type"] == "WARNING"
    assert warning[0]["usage_percentage"] == "80.00"

    _expense(client, auth_headers, wallet["id"], category["id"], "20.00")
    crossed = _alerts(client, auth_headers)
    assert {item["alert_type"] for item in crossed} == {"WARNING", "EXCEEDED"}
    assert {item["spent_amount"] for item in crossed} == {"100.00"}

    _expense(client, auth_headers, wallet["id"], category["id"], "5.00")
    deduplicated = _alerts(client, auth_headers)
    assert len(deduplicated) == 2
    assert {item["spent_amount"] for item in deduplicated} == {"105.00"}


def test_global_budget_tracks_categorized_and_uncategorized_expenses(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    response = client.post(
        "/api/v1/budgets/",
        json={"limit_amount": "100.00", "alert_threshold": 80},
        headers=auth_headers,
    )
    assert response.status_code == 201
    budget = response.json()
    assert budget["category_id"] is None

    _expense(client, auth_headers, wallet["id"], category["id"], "50.00")
    _expense(client, auth_headers, wallet["id"], None, "30.00")

    status = client.get(f"/api/v1/budgets/{budget['id']}/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["category_id"] is None
    assert status.json()["spent_amount"] == "80.00"
    alerts = _alerts(client, auth_headers)
    assert len(alerts) == 1
    assert alerts[0]["category_id"] is None
    assert alerts[0]["alert_type"] == "WARNING"


def test_alert_inbox_read_operations_and_ownership(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _create_budget(client, auth_headers, category["id"])
    _expense(client, auth_headers, wallet["id"], category["id"], "100.00")
    alerts = _alerts(client, auth_headers)
    assert len(alerts) == 2

    count = client.get("/api/v1/budget-alerts/unread-count", headers=auth_headers)
    assert count.json() == {"unread_count": 2}

    read_one = client.patch(
        f"/api/v1/budget-alerts/{alerts[0]['id']}/read", headers=auth_headers
    )
    assert read_one.status_code == 200
    assert read_one.json()["read_at"] is not None
    assert client.get(
        "/api/v1/budget-alerts/unread-count", headers=auth_headers
    ).json() == {"unread_count": 1}

    other_headers = _other_user_headers(client)
    assert (
        client.patch(
            f"/api/v1/budget-alerts/{alerts[1]['id']}/read", headers=other_headers
        ).status_code
        == 404
    )

    read_all = client.post("/api/v1/budget-alerts/read-all", headers=auth_headers)
    assert read_all.status_code == 200
    assert read_all.json() == {"updated": 1}
    assert client.get(
        "/api/v1/budget-alerts/?unread_only=true", headers=auth_headers
    ).json() == []


def test_transaction_correction_resolves_and_recrossing_reactivates_alert(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _create_budget(client, auth_headers, category["id"])
    transaction = _expense(
        client, auth_headers, wallet["id"], category["id"], "100.00"
    )
    assert len(_alerts(client, auth_headers)) == 2
    client.post("/api/v1/budget-alerts/read-all", headers=auth_headers)

    corrected = client.put(
        f"/api/v1/transactions/{transaction['id']}",
        json={"amount": "10.00"},
        headers=auth_headers,
    )
    assert corrected.status_code == 200
    assert _alerts(client, auth_headers) == []
    historical = _alerts(client, auth_headers, active_only=False)
    assert len(historical) == 2
    assert all(item["resolved_at"] is not None for item in historical)

    recrossed = client.put(
        f"/api/v1/transactions/{transaction['id']}",
        json={"amount": "90.00"},
        headers=auth_headers,
    )
    assert recrossed.status_code == 200
    active = _alerts(client, auth_headers)
    assert len(active) == 1
    assert active[0]["alert_type"] == "WARNING"
    assert active[0]["read_at"] is None
    assert active[0]["resolved_at"] is None


def test_transaction_deletion_resolves_alerts(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _create_budget(client, auth_headers, category["id"], threshold=50)
    transaction = _expense(
        client, auth_headers, wallet["id"], category["id"], "60.00"
    )
    assert len(_alerts(client, auth_headers)) == 1
    deleted = client.delete(
        f"/api/v1/transactions/{transaction['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert _alerts(client, auth_headers) == []


def test_disabled_alerts_still_expose_live_budget_status(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    budget = _create_budget(
        client, auth_headers, category["id"], limit="50.00", enabled=False
    )
    _expense(client, auth_headers, wallet["id"], category["id"], "60.00")
    assert _alerts(client, auth_headers) == []
    status = client.get(f"/api/v1/budgets/{budget['id']}/status", headers=auth_headers)
    assert status.json()["status"] == "EXCEEDED"
    assert status.json()["remaining_amount"] == "0.00"
    assert status.json()["usage_percentage"] == "120.00"


def test_budget_creation_and_configuration_reconcile_existing_expenses(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _expense(client, auth_headers, wallet["id"], category["id"], "60.00")
    budget = _create_budget(client, auth_headers, category["id"], threshold=50)
    assert [item["alert_type"] for item in _alerts(client, auth_headers)] == ["WARNING"]

    disabled = client.put(
        f"/api/v1/budgets/{budget['id']}",
        json={"alerts_enabled": False},
        headers=auth_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["alerts_enabled"] is False
    assert _alerts(client, auth_headers) == []

    enabled = client.put(
        f"/api/v1/budgets/{budget['id']}",
        json={"alerts_enabled": True, "alert_threshold": 70},
        headers=auth_headers,
    )
    assert enabled.status_code == 200
    assert _alerts(client, auth_headers) == []

    lowered = client.put(
        f"/api/v1/budgets/{budget['id']}",
        json={"alert_threshold": 60},
        headers=auth_headers,
    )
    assert lowered.status_code == 200
    assert len(_alerts(client, auth_headers)) == 1


def test_weekly_status_uses_user_calendar_boundaries(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    today = date.today()
    budget = _create_budget(
        client, auth_headers, category["id"], period="WEEKLY", threshold=50
    )
    _expense(
        client,
        auth_headers,
        wallet["id"],
        category["id"],
        "25.00",
        occurred_at=f"{today.isoformat()}T12:00:00",
    )
    current = client.get(
        f"/api/v1/budgets/{budget['id']}/status?on_date={today.isoformat()}",
        headers=auth_headers,
    )
    assert current.status_code == 200
    assert current.json()["spent_amount"] == "25.00"
    assert current.json()["period_start"] == (today - timedelta(days=today.weekday())).isoformat()

    next_week = today + timedelta(days=7)
    later = client.get(
        f"/api/v1/budgets/{budget['id']}/status?on_date={next_week.isoformat()}",
        headers=auth_headers,
    )
    assert later.status_code == 200
    assert later.json()["spent_amount"] == "0.00"


def test_confirmed_csv_import_generates_budget_alert(
    client: TestClient,
    auth_headers: dict[str, str],
    wallet: dict,
    category: dict,
):
    _create_budget(client, auth_headers, category["id"], threshold=80)
    today = date.today().strftime("%d/%m/%Y")
    statement = f"Data;Descricao;Valor;ID\n{today};Imported expense;-85,00;alert-import-1\n"
    preview = client.post(
        "/api/v1/imports/",
        data={"wallet_id": str(wallet["id"])},
        files={"file": ("alerts.csv", statement.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert preview.status_code == 201
    confirmed = client.post(
        f"/api/v1/imports/{preview.json()['batch']['id']}/confirm",
        json={"default_category_id": category["id"]},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    alerts = _alerts(client, auth_headers)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "WARNING"
    assert alerts[0]["spent_amount"] == "85.00"


def test_budget_alert_settings_validation(
    client: TestClient, auth_headers: dict[str, str], category: dict
):
    for threshold in (0, 100):
        response = client.post(
            "/api/v1/budgets/",
            json={
                "category_id": category["id"],
                "limit_amount": "100.00",
                "alert_threshold": threshold,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
    assert client.get("/api/v1/budget-alerts/").status_code == 401
