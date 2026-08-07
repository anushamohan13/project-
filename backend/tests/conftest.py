import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_financial_planner.db"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough"
os.environ["ENVIRONMENT"] = "test"
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def remove_test_database_after_session():
    yield
    engine.dispose()
    Path("test_financial_planner.db").unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    response = client.post("/api/auth/dev-login", json={"email": "test@example.com", "username": "tester"})
    token = response.json()["access_token"]
    client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "tester",
            "country": "Singapore",
            "city": "Singapore",
            "currency": "SGD",
            "timezone": "Asia/Singapore",
            "current_balance": "500.00",
            "normal_savings_percent": "20.00",
            "emergency_savings_minimum": "100.00",
            "savings_before_discretionary": True,
            "theme_mode": "system"
        },
    )
    return {"Authorization": f"Bearer {token}"}
