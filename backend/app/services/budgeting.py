from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from app.models.entities import Activity, ActivityPriority, IncomeFrequency, IncomeStream, RecurringExpense
from app.schemas.common import money, percentage


@dataclass(frozen=True)
class BudgetAllocationValue:
    category: str
    amount: Decimal
    locked: bool = False
    informational: bool = False


@dataclass(frozen=True)
class BudgetComputation:
    period_start: date
    period_end: date
    currency: str
    income_for_period: Decimal
    current_balance: Decimal
    total_available: Decimal
    remaining_balance: Decimal
    overspending_amount: Decimal
    projected_balance_before_next_salary: Decimal
    required_reduction: Decimal
    allocations: tuple[BudgetAllocationValue, ...]
    warnings: tuple[str, ...]


def _monthly_events(first_date: date, day_of_month: int, start: date, end: date) -> list[date]:
    year, month = first_date.year, first_date.month
    events: list[date] = []
    while date(year, month, min(day_of_month, monthrange(year, month)[1])) < start:
        month += 1
        if month > 12:
            month = 1
            year += 1
    while True:
        scheduled = date(year, month, min(day_of_month, monthrange(year, month)[1]))
        if scheduled > end:
            break
        if scheduled >= max(start, first_date):
            events.append(scheduled)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return events


def recurring_events(first_date: date, frequency: IncomeFrequency, start: date, end: date, day_of_month: int | None = None) -> list[date]:
    events: list[date] = []
    current = first_date
    if frequency in {IncomeFrequency.weekly, IncomeFrequency.fortnightly}:
        step = 7 if frequency == IncomeFrequency.weekly else 14
        while current < start:
            current += timedelta(days=step)
        while current <= end:
            events.append(current)
            current += timedelta(days=step)
        return events
    return _monthly_events(first_date, day_of_month or first_date.day, start, end)


def _income_events(stream: IncomeStream, start: date, end: date) -> list[date]:
    if not stream.is_active:
        return []
    return recurring_events(stream.next_payment_date, stream.frequency, start, end, stream.payment_day_of_month)


def income_for_period(incomes: Iterable[IncomeStream], start: date, end: date, planning_currency: str) -> Decimal:
    total = Decimal("0.00")
    for stream in incomes:
        if stream.currency != planning_currency:
            raise ValueError(f"No verified exchange rate available for {stream.currency}/{planning_currency}")
        total += stream.amount * len(_income_events(stream, start, end))
    return money(total)


def recurring_expense_for_period(
    expenses: Iterable[RecurringExpense], start: date, end: date, planning_currency: str
) -> tuple[Decimal, Decimal]:
    essential = Decimal("0.00")
    flexible = Decimal("0.00")
    for expense in expenses:
        if not expense.is_active:
            continue
        if expense.currency != planning_currency:
            raise ValueError(f"No verified exchange rate available for {expense.currency}/{planning_currency}")
        count = len(recurring_events(expense.next_due_date, expense.frequency, start, end, expense.next_due_date.day))
        amount = money(expense.amount * count)
        if expense.is_essential:
            essential += amount
        else:
            flexible += amount
    return money(essential), money(flexible)


def calculate_budget(
    *,
    period_start: date,
    period_end: date,
    planning_currency: str,
    current_balance: Decimal,
    savings_percent: Decimal,
    incomes: Iterable[IncomeStream],
    activities: Iterable[Activity],
    recurring_expenses: Iterable[RecurringExpense] = (),
    wishlist_contribution: Decimal = Decimal("0.00"),
) -> BudgetComputation:
    if period_end < period_start:
        raise ValueError("period_end must not be before period_start")

    incomes = list(incomes)
    activities = list(activities)
    recurring_expenses = list(recurring_expenses)
    income = income_for_period(incomes, period_start, period_end, planning_currency)
    total_available = money(current_balance + income)

    essential = Decimal("0.00")
    important = Decimal("0.00")
    optional = Decimal("0.00")
    online_shopping = Decimal("0.00")
    bills = Decimal("0.00")

    for activity in activities:
        if not (period_start <= activity.activity_date <= period_end):
            continue
        if activity.currency != planning_currency:
            raise ValueError(f"No verified exchange rate available for {activity.currency}/{planning_currency}")
        completed = bool(getattr(activity, "completed", False))
        actual_cost = getattr(activity, "actual_cost", None)
        cost = money(actual_cost if completed and actual_cost is not None else activity.estimated_cost)
        category = activity.category.strip().lower()
        if "bill" in category or category in {"utilities", "insurance", "mortgage", "rent"}:
            bills += cost
        elif "online" in category:
            online_shopping += cost
        elif activity.priority == ActivityPriority.essential:
            essential += cost
        elif activity.priority == ActivityPriority.important:
            important += cost
        else:
            optional += cost

    recurring_essential, recurring_flexible = recurring_expense_for_period(
        recurring_expenses, period_start, period_end, planning_currency
    )
    bills += recurring_essential
    important += recurring_flexible

    normal_savings = money(income * (savings_percent / Decimal("100")))
    wishlist = money(wishlist_contribution)
    essential = money(essential)
    planned_activities = money(important + optional)
    online_shopping = money(online_shopping)
    bills = money(bills)

    committed = essential + planned_activities + online_shopping + bills + normal_savings + wishlist
    original_remaining = money(total_available - committed)
    overspending = money(max(Decimal("0.00"), -original_remaining))
    positive_remaining = money(max(Decimal("0.00"), original_remaining))

    funded = {
        "Essential expenses": essential,
        "Bills": bills,
        "Planned activities": planned_activities,
        "Online shopping": online_shopping,
        "Normal savings": normal_savings,
        "Smart Wishlist savings": wishlist,
    }
    reduction_remaining = overspending
    reductions: list[tuple[str, Decimal]] = []
    for category in ("Online shopping", "Planned activities", "Smart Wishlist savings", "Normal savings"):
        reduction = min(funded[category], reduction_remaining)
        if reduction > 0:
            funded[category] = money(funded[category] - reduction)
            reduction_remaining = money(reduction_remaining - reduction)
            reductions.append((category, reduction))
    if reduction_remaining > 0:
        for category in ("Essential expenses", "Bills"):
            reduction = min(funded[category], reduction_remaining)
            if reduction > 0:
                funded[category] = money(funded[category] - reduction)
                reduction_remaining = money(reduction_remaining - reduction)
                reductions.append((category, reduction))

    allocations = (
        BudgetAllocationValue("Essential expenses", funded["Essential expenses"], True),
        BudgetAllocationValue("Bills", funded["Bills"], True),
        BudgetAllocationValue("Planned activities", funded["Planned activities"]),
        BudgetAllocationValue("Online shopping", funded["Online shopping"]),
        BudgetAllocationValue("Normal savings", funded["Normal savings"], True),
        BudgetAllocationValue("Smart Wishlist savings", funded["Smart Wishlist savings"]),
        BudgetAllocationValue("Remaining available balance", positive_remaining),
        BudgetAllocationValue("Overspending", overspending, False, True),
    )

    warnings: list[str] = []
    if overspending > 0:
        warnings.append(f"The original plan exceeds available funds by {planning_currency} {overspending}.")
        if reductions:
            summary = ", ".join(f"{category}: {planning_currency} {amount}" for category, amount in reductions)
            warnings.append(f"The displayed funded allocation fits available funds by reducing: {summary}.")
    if normal_savings > 0 and positive_remaining == 0 and overspending == 0:
        warnings.append("The plan uses all available funds and leaves no discretionary buffer.")
    if not incomes:
        warnings.append("No active income payment falls within this planning period.")

    return BudgetComputation(
        period_start=period_start,
        period_end=period_end,
        currency=planning_currency,
        income_for_period=income,
        current_balance=money(current_balance),
        total_available=total_available,
        remaining_balance=positive_remaining,
        overspending_amount=overspending,
        projected_balance_before_next_salary=original_remaining,
        required_reduction=overspending,
        allocations=allocations,
        warnings=tuple(warnings),
    )


def allocation_percent(amount: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal("0.00")
    return percentage((amount / total) * Decimal("100"))


def validate_confirmed_allocations(
    total_available: Decimal, allocations: Iterable[tuple[str, Decimal, bool]]
) -> tuple[Decimal, Decimal]:
    allocation_list = list(allocations)
    total_allocated = money(
        sum((money(amount) for _, amount, informational in allocation_list if not informational), Decimal("0.00"))
    )
    if total_allocated != money(total_available):
        raise ValueError(f"Funded allocation total {total_allocated} must exactly equal available total {money(total_available)}")
    overspending = next(
        (money(amount) for category, amount, _ in allocation_list if category.lower() == "overspending"),
        Decimal("0.00"),
    )
    remaining = next(
        (money(amount) for category, amount, _ in allocation_list if category.lower() == "remaining available balance"),
        Decimal("0.00"),
    )
    return remaining, overspending
