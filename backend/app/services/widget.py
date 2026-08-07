import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BudgetPlan, IncomeStream, WidgetSnapshot, WishlistItem
from app.schemas.common import money, percentage


def update_widget_snapshot(db: Session, user_id: str, plan: BudgetPlan) -> WidgetSnapshot:
    allocations = {item.category: money(item.amount) for item in plan.allocations}
    savings = allocations.get("Normal savings", Decimal("0.00"))
    total = money(plan.total_available)

    wishlist_items = db.scalars(
        select(WishlistItem).where(WishlistItem.user_id == user_id, WishlistItem.status == "active")
    ).all()
    wishlist_total = sum((item.price for item in wishlist_items), Decimal("0.00"))
    wishlist_saved = sum((item.amount_saved for item in wishlist_items), Decimal("0.00"))

    next_salary = db.scalar(
        select(IncomeStream.next_payment_date)
        .where(
            IncomeStream.user_id == user_id,
            IncomeStream.is_active.is_(True),
            IncomeStream.next_payment_date >= date.today(),
        )
        .order_by(IncomeStream.next_payment_date.asc())
    )
    snapshot_data = {
        "plan_id": plan.id,
        "plan_version": plan.version,
        "weekly_allowance": str(money(plan.remaining_balance)),
        "remaining_budget": str(money(plan.remaining_balance)),
        "savings_progress_percent": str(percentage((savings / total) * 100) if total > 0 else Decimal("0.00")),
        "wishlist_progress_percent": str(
            percentage((wishlist_saved / wishlist_total) * 100) if wishlist_total > 0 else Decimal("0.00")
        ),
        "next_salary_date": next_salary.isoformat() if next_salary else None,
        "currency": plan.currency,
    }

    snapshot = db.scalar(select(WidgetSnapshot).where(WidgetSnapshot.user_id == user_id))
    if snapshot is None:
        snapshot = WidgetSnapshot(user_id=user_id, **{key: value for key, value in snapshot_data.items() if key != "next_salary_date"})
        snapshot.next_salary_date = next_salary
        db.add(snapshot)
    else:
        snapshot.plan_id = plan.id
        snapshot.plan_version = plan.version
        snapshot.weekly_allowance = money(plan.remaining_balance)
        snapshot.remaining_budget = money(plan.remaining_balance)
        snapshot.savings_progress_percent = Decimal(snapshot_data["savings_progress_percent"])
        snapshot.wishlist_progress_percent = Decimal(snapshot_data["wishlist_progress_percent"])
        snapshot.next_salary_date = next_salary
        snapshot.currency = plan.currency
    snapshot.snapshot_json = json.dumps(snapshot_data, sort_keys=True)
    db.flush()
    return snapshot
