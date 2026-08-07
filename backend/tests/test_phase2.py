from datetime import date, datetime, timedelta, timezone


def create_base_plan(client, headers):
    today = date.today()
    client.post(
        "/api/income-streams",
        headers=headers,
        json={
            "name": "Salary",
            "amount": "1000.00",
            "currency": "SGD",
            "frequency": "weekly",
            "payment_weekday": today.weekday(),
            "payment_day_of_month": None,
            "next_payment_date": today.isoformat(),
            "is_active": True,
            "notes": None,
        },
    )
    client.post(
        "/api/activities",
        headers=headers,
        json={
            "name": "Dinner",
            "category": "Dining",
            "activity_date": today.isoformat(),
            "city": "Singapore",
            "people_count": 2,
            "estimated_cost": "200.00",
            "actual_cost": None,
            "currency": "SGD",
            "manually_entered": True,
            "recurring": False,
            "priority": "optional",
            "completed": False,
            "notes": None,
        },
    )
    calculated = client.post(
        "/api/budgets/calculate",
        headers=headers,
        json={
            "period_start": today.isoformat(),
            "period_end": (today + timedelta(days=6)).isoformat(),
            "wishlist_contribution": "50.00",
        },
    ).json()
    response = client.post(
        "/api/budgets/confirm",
        headers=headers,
        json={
            "period_start": calculated["period_start"],
            "period_end": calculated["period_end"],
            "currency": calculated["currency"],
            "total_available": calculated["total_available"],
            "allocations": [
                {key: item[key] for key in ["category", "amount", "locked", "informational"]}
                for item in calculated["allocations"]
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_refresh_token_rotation_rejects_reuse(client):
    login = client.post("/api/auth/dev-login", json={"email": "rotate@example.com", "username": "rotate"}).json()
    first = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert first.status_code == 200, first.text
    reused = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert reused.status_code == 401


def test_transaction_crud_summary_and_custom_category(client, auth_headers):
    category = client.post(
        "/api/categories",
        headers=auth_headers,
        json={"name": "Pets", "icon": "paw", "color_token": "orange", "is_essential": True, "is_active": True},
    )
    assert category.status_code == 201, category.text

    transaction = client.post(
        "/api/transactions",
        headers=auth_headers,
        json={
            "merchant": "Pet shop",
            "amount": "80.50",
            "currency": "SGD",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "category": "Pets",
            "payment_method": "Card",
            "is_online": True,
            "kind": "expense",
            "related_activity_id": None,
            "receipt_image_url": None,
            "notes": None,
        },
    )
    assert transaction.status_code == 201, transaction.text
    transaction_id = transaction.json()["id"]
    summary = client.get("/api/transactions/summary", headers=auth_headers).json()
    assert summary["total_expenses"] == "80.50"
    assert summary["online_spending"] == "80.50"
    assert summary["by_category"]["Pets"] == "80.50"
    assert client.delete(f"/api/transactions/{transaction_id}", headers=auth_headers).status_code == 204


def test_ai_proposal_confirmation_and_reversal(client, auth_headers):
    base = create_base_plan(client, auth_headers)
    response = client.post(
        "/api/chat/messages",
        headers=auth_headers,
        json={"message": "Move SGD 50 from Planned activities to Smart Wishlist savings."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_confirmation"] is True
    proposal_id = body["proposal_id"]

    confirmed = client.post(f"/api/chat/proposals/{proposal_id}/confirm", headers=auth_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["plan"]["version"] == base["version"] + 1
    assert confirmed.json()["proposal"]["status"] == "applied"

    reversed_response = client.post(f"/api/chat/proposals/{proposal_id}/reverse", headers=auth_headers)
    assert reversed_response.status_code == 200, reversed_response.text
    assert reversed_response.json()["proposal"]["status"] == "reversed"
    assert reversed_response.json()["plan"]["version"] == base["version"] + 2


def test_budget_history_comparison(client, auth_headers):
    first = create_base_plan(client, auth_headers)
    allocations = first["allocations"]
    remaining = next(item for item in allocations if item["category"] == "Remaining available balance")
    shopping = next(item for item in allocations if item["category"] == "Online shopping")
    remaining["amount"] = f"{float(remaining['amount']) - 10:.2f}"
    shopping["amount"] = f"{float(shopping['amount']) + 10:.2f}"
    second_response = client.post(
        "/api/budgets/confirm",
        headers=auth_headers,
        json={
            "period_start": first["period_start"],
            "period_end": first["period_end"],
            "currency": first["currency"],
            "total_available": first["total_available"],
            "allocations": allocations,
        },
    )
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    comparison = client.get(
        f"/api/budgets/compare?left_id={first['id']}&right_id={second['id']}", headers=auth_headers
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["right_plan"]["version"] == second["version"]


def test_mock_email_job(client, auth_headers):
    queued = client.post(
        "/api/notifications/jobs",
        headers=auth_headers,
        json={
            "channel": "email",
            "template_key": "weekly_planning_reminder",
            "recipient": None,
            "payload": {},
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert queued.status_code == 201, queued.text
    processed = client.post("/api/notifications/run-due", headers=auth_headers)
    assert processed.status_code == 200
    job = client.get(f"/api/notifications/jobs/{queued.json()['id']}", headers=auth_headers).json()
    assert job["status"] == "sent"
