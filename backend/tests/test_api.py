from datetime import date, timedelta


def test_end_to_end_phase_one_flow(client, auth_headers):
    today = date.today()
    income = client.post(
        "/api/income-streams",
        headers=auth_headers,
        json={
            "name": "Main Salary",
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
    assert income.status_code == 201, income.text

    activity = client.post(
        "/api/activities",
        headers=auth_headers,
        json={
            "name": "Groceries",
            "category": "Groceries",
            "activity_date": today.isoformat(),
            "city": "Singapore",
            "people_count": 2,
            "estimated_cost": "150.00",
            "currency": "SGD",
            "manually_entered": True,
            "recurring": False,
            "priority": "essential",
            "notes": None,
        },
    )
    assert activity.status_code == 201, activity.text

    calculated = client.post(
        "/api/budgets/calculate",
        headers=auth_headers,
        json={
            "period_start": today.isoformat(),
            "period_end": (today + timedelta(days=6)).isoformat(),
            "wishlist_contribution": "50.00",
        },
    )
    assert calculated.status_code == 200, calculated.text
    body = calculated.json()
    assert body["total_available"] == "1500.00"

    confirmed = client.post(
        "/api/budgets/confirm",
        headers=auth_headers,
        json={
            "period_start": body["period_start"],
            "period_end": body["period_end"],
            "currency": body["currency"],
            "total_available": body["total_available"],
            "allocations": [
                {"category": item["category"], "amount": item["amount"], "locked": item["locked"], "informational": item["informational"]}
                for item in body["allocations"]
            ],
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["version"] == 1

    widget = client.get("/api/widget/snapshot", headers=auth_headers)
    assert widget.status_code == 200
    assert widget.json()["currency"] == "SGD"


def test_cross_user_income_isolation(client):
    a = client.post("/api/auth/dev-login", json={"email": "a@example.com", "username": "usera"}).json()["access_token"]
    b = client.post("/api/auth/dev-login", json={"email": "b@example.com", "username": "userb"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {a}"}
    headers_b = {"Authorization": f"Bearer {b}"}
    today = date.today().isoformat()
    created = client.post("/api/income-streams", headers=headers_a, json={
        "name": "Private Income", "amount": "200.00", "currency": "SGD", "frequency": "weekly",
        "payment_weekday": date.today().weekday(), "payment_day_of_month": None,
        "next_payment_date": today, "is_active": True, "notes": None
    })
    assert created.status_code == 201
    assert client.get("/api/income-streams", headers=headers_b).json() == []


def test_affordability_chat_parses_comma_amount(client, auth_headers):
    response = client.post(
        "/api/chat/messages",
        headers=auth_headers,
        json={"message": "Can I afford a laptop costing SGD 1,500?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "calculate_affordability"
    assert body["data"]["requested_change"]["purchase_cost"] == "1500"
    assert body["data"]["financial_impact"]["shortfall"] == "1000.00"
