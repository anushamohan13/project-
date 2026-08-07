import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import BudgetAllocation, BudgetPlan, PlanStatus, User
from app.schemas.common import money, percentage
from app.schemas.finance import AllocationInput, BudgetComparisonItem
from app.services.audit import record_audit
from app.services.budgeting import validate_confirmed_allocations
from app.services.widget import update_widget_snapshot


def latest_plan(db: Session, user_id: str) -> BudgetPlan | None:
    return db.scalar(
        select(BudgetPlan)
        .options(selectinload(BudgetPlan.allocations))
        .where(BudgetPlan.user_id == user_id, BudgetPlan.status != PlanStatus.archived)
        .order_by(BudgetPlan.version.desc())
    )


def get_plan_owned(db: Session, user_id: str, plan_id: str) -> BudgetPlan:
    plan = db.scalar(
        select(BudgetPlan)
        .options(selectinload(BudgetPlan.allocations))
        .where(BudgetPlan.id == plan_id, BudgetPlan.user_id == user_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Budget plan not found")
    return plan


def plan_snapshot(plan: BudgetPlan | None) -> dict:
    if plan is None:
        return {
            "id": None,
            "version": None,
            "period_start": None,
            "period_end": None,
            "currency": None,
            "total_available": "0.00",
            "remaining_balance": "0.00",
            "overspending_amount": "0.00",
            "allocations": [],
        }
    return {
        "id": plan.id,
        "version": plan.version,
        "period_start": plan.period_start.isoformat(),
        "period_end": plan.period_end.isoformat(),
        "currency": plan.currency,
        "total_available": str(money(plan.total_available)),
        "remaining_balance": str(money(plan.remaining_balance)),
        "overspending_amount": str(money(plan.overspending_amount)),
        "allocations": [
            {
                "category": allocation.category,
                "amount": str(money(allocation.amount)),
                "locked": allocation.locked,
                "informational": allocation.informational,
            }
            for allocation in plan.allocations
        ],
    }


def create_confirmed_plan(
    db: Session,
    *,
    user: User,
    period_start,
    period_end,
    currency: str,
    total_available: Decimal,
    allocations: Iterable[AllocationInput | dict],
    source: str = "manual",
    source_proposal_id: str | None = None,
    previous_plan_id: str | None = None,
) -> BudgetPlan:
    normalized: list[dict] = []
    for item in allocations:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        normalized.append(
            {
                "category": data["category"],
                "amount": money(data["amount"]),
                "locked": bool(data.get("locked", False)),
                "informational": bool(data.get("informational", False)),
            }
        )
    try:
        remaining, overspending = validate_confirmed_allocations(
            total_available,
            [(item["category"], item["amount"], item["informational"]) for item in normalized],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    current_version = db.scalar(select(func.max(BudgetPlan.version)).where(BudgetPlan.user_id == user.id)) or 0
    plan = BudgetPlan(
        user_id=user.id,
        version=current_version + 1,
        period_start=period_start,
        period_end=period_end,
        currency=currency.upper(),
        total_available=money(total_available),
        remaining_balance=remaining,
        overspending_amount=overspending,
        status=PlanStatus.confirmed,
        source=source,
        source_proposal_id=source_proposal_id,
        previous_plan_id=previous_plan_id,
        confirmed_at=datetime.now(timezone.utc),
    )
    plan.allocations = [BudgetAllocation(**item) for item in normalized]
    db.add(plan)
    db.flush()
    update_widget_snapshot(db, user.id, plan)
    record_audit(
        db,
        user_id=user.id,
        action="budget_plan.confirmed",
        entity_type="BudgetPlan",
        entity_id=plan.id,
        detail={"version": plan.version, "source": source, "proposal_id": source_proposal_id},
    )
    return plan


def compare_plans(left: BudgetPlan, right: BudgetPlan) -> tuple[Decimal, Decimal, list[BudgetComparisonItem]]:
    left_map = {item.category: money(item.amount) for item in left.allocations}
    right_map = {item.category: money(item.amount) for item in right.allocations}
    changes: list[BudgetComparisonItem] = []
    for category in sorted(set(left_map) | set(right_map)):
        left_amount = left_map.get(category, Decimal("0.00"))
        right_amount = right_map.get(category, Decimal("0.00"))
        difference = money(right_amount - left_amount)
        percent_change = None if left_amount == 0 else percentage((difference / left_amount) * Decimal("100"))
        changes.append(
            BudgetComparisonItem(
                category=category,
                left_amount=left_amount,
                right_amount=right_amount,
                difference=difference,
                percent_change=percent_change,
            )
        )
    return (
        money(right.total_available - left.total_available),
        money(right.remaining_balance - left.remaining_balance),
        changes,
    )


def allocations_from_snapshot(snapshot: dict) -> list[dict]:
    return [
        {
            "category": item["category"],
            "amount": money(item["amount"]),
            "locked": bool(item.get("locked", False)),
            "informational": bool(item.get("informational", False)),
        }
        for item in snapshot.get("allocations", [])
    ]


def dump_json(data: dict) -> str:
    return json.dumps(data, default=str, sort_keys=True)
