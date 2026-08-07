from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.entities import ActivityPriority, IncomeFrequency
from app.services.budgeting import calculate_budget, validate_confirmed_allocations


def test_weekly_budget_uses_decimal_and_balances():
    income = SimpleNamespace(
        is_active=True,
        amount=Decimal("1000.00"),
        currency="SGD",
        frequency=IncomeFrequency.weekly,
        next_payment_date=date(2026, 8, 7),
        payment_day_of_month=None,
    )
    activities = [
        SimpleNamespace(activity_date=date(2026, 8, 8), currency="SGD", estimated_cost=Decimal("200.00"), category="Groceries", priority=ActivityPriority.essential),
        SimpleNamespace(activity_date=date(2026, 8, 9), currency="SGD", estimated_cost=Decimal("75.55"), category="Dining", priority=ActivityPriority.optional),
    ]
    result = calculate_budget(
        period_start=date(2026, 8, 7),
        period_end=date(2026, 8, 13),
        planning_currency="SGD",
        current_balance=Decimal("100.00"),
        savings_percent=Decimal("20.00"),
        incomes=[income],
        activities=activities,
        wishlist_contribution=Decimal("50.00"),
    )
    assert result.total_available == Decimal("1100.00")
    assert result.remaining_balance == Decimal("574.45")
    assert result.overspending_amount == Decimal("0.00")
    assert sum(item.amount for item in result.allocations if not item.informational) == Decimal("1100.00")


def test_overspending_is_explicit():
    income = SimpleNamespace(
        is_active=True,
        amount=Decimal("500.00"),
        currency="SGD",
        frequency=IncomeFrequency.weekly,
        next_payment_date=date(2026, 8, 7),
        payment_day_of_month=None,
    )
    activities = [
        SimpleNamespace(activity_date=date(2026, 8, 8), currency="SGD", estimated_cost=Decimal("600.00"), category="Shopping", priority=ActivityPriority.optional),
    ]
    result = calculate_budget(
        period_start=date(2026, 8, 7),
        period_end=date(2026, 8, 13),
        planning_currency="SGD",
        current_balance=Decimal("0.00"),
        savings_percent=Decimal("20.00"),
        incomes=[income],
        activities=activities,
    )
    assert result.overspending_amount == Decimal("200.00")
    assert result.required_reduction == Decimal("200.00")
    assert sum(item.amount for item in result.allocations if not item.informational) == Decimal("500.00")


def test_confirmation_requires_exact_total():
    with pytest.raises(ValueError):
        validate_confirmed_allocations(Decimal("100.00"), [("Normal savings", Decimal("30.00"), False), ("Remaining available balance", Decimal("60.00"), False)])
