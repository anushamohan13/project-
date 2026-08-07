import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from difflib import get_close_matches
from typing import Callable

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import FinancialChangeProposal, ProposalStatus, User
from app.schemas.common import money, percentage
from app.services.audit import record_audit
from app.services.plans import latest_plan, plan_snapshot

settings = get_settings()


class AmountArgs(BaseModel):
    amount: Decimal = Field(gt=0)


class EmergencyArgs(AmountArgs):
    description: str = Field(min_length=1, max_length=1000)
    protect_essentials: bool = True


class TransferArgs(AmountArgs):
    from_category: str = Field(min_length=1, max_length=80)
    to_category: str = Field(min_length=1, max_length=80)


class ReductionArgs(AmountArgs):
    category: str = Field(min_length=1, max_length=80)


class SavingsPercentArgs(BaseModel):
    percentage: Decimal = Field(ge=0, le=100)


def _allocation_map(snapshot: dict) -> dict[str, dict]:
    return {item["category"]: dict(item) for item in snapshot.get("allocations", [])}


def _resolve_category(allocations: dict[str, dict], requested: str) -> str:
    lowered = {key.lower(): key for key in allocations}
    if requested.lower() in lowered:
        return lowered[requested.lower()]
    matches = get_close_matches(requested.lower(), list(lowered), n=1, cutoff=0.45)
    if matches:
        return lowered[matches[0]]
    raise HTTPException(status_code=422, detail=f"Budget category '{requested}' was not found")


def _new_proposal(
    db: Session,
    *,
    user: User,
    request: str,
    intent: str,
    before: dict,
    proposed: dict,
    calculation: dict,
    conversation_id: str | None,
) -> FinancialChangeProposal:
    proposal = FinancialChangeProposal(
        user_id=user.id,
        conversation_id=conversation_id,
        original_request=request,
        interpreted_intent=intent,
        status=ProposalStatus.awaiting_confirmation,
        base_plan_id=before.get("id"),
        base_plan_version=before.get("version"),
        before_plan_json=json.dumps(before, sort_keys=True),
        proposed_plan_json=json.dumps(proposed, sort_keys=True),
        calculation_json=json.dumps(calculation, sort_keys=True),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.proposal_expiry_minutes),
    )
    db.add(proposal)
    db.flush()
    record_audit(
        db,
        user_id=user.id,
        action="financial_change_proposal.created",
        entity_type="FinancialChangeProposal",
        entity_id=proposal.id,
        detail={"intent": intent, "base_plan_version": before.get("version")},
    )
    return proposal


def get_financial_summary(db: Session, user: User, arguments: dict, **_: object) -> dict:
    plan = latest_plan(db, user.id)
    profile = user.profile
    currency = profile.currency if profile else "SGD"
    current_balance = money(profile.current_balance if profile else 0)
    if plan:
        available = money(plan.remaining_balance)
        return {
            "currency": plan.currency,
            "current_balance": str(current_balance),
            "latest_plan_version": plan.version,
            "total_available": str(plan.total_available),
            "remaining_balance": str(plan.remaining_balance),
            "overspending_amount": str(plan.overspending_amount),
            "allocations": plan_snapshot(plan)["allocations"],
        }
    return {
        "currency": currency,
        "current_balance": str(current_balance),
        "latest_plan_version": None,
        "total_available": str(current_balance),
        "remaining_balance": str(current_balance),
        "overspending_amount": "0.00",
        "allocations": [],
    }


def calculate_affordability(db: Session, user: User, arguments: dict, **_: object) -> dict:
    args = AmountArgs.model_validate(arguments)
    plan = latest_plan(db, user.id)
    profile = user.profile
    currency = plan.currency if plan else (profile.currency if profile else "SGD")
    available = money(plan.remaining_balance if plan else (profile.current_balance if profile else 0))
    cost = money(args.amount)
    shortfall = money(max(Decimal("0.00"), cost - available))
    return {
        "currency": currency,
        "purchase_cost": str(cost),
        "available_balance": str(available),
        "shortfall": str(shortfall),
        "affordable": shortfall == 0,
        "current_position": {"available_balance": str(available), "currency": currency},
        "requested_change": {"purchase_cost": str(args.amount)},
        "financial_impact": {"shortfall": str(shortfall), "affordable": shortfall == 0},
    }


def create_budget_transfer_proposal(
    db: Session, user: User, arguments: dict, *, original_request: str, conversation_id: str | None = None
) -> dict:
    args = TransferArgs.model_validate(arguments)
    plan = latest_plan(db, user.id)
    if not plan:
        raise HTTPException(status_code=409, detail="Confirm a budget plan before requesting allocation changes")
    before = plan_snapshot(plan)
    allocations = _allocation_map(before)
    source = _resolve_category(allocations, args.from_category)
    target = _resolve_category(allocations, args.to_category) if args.to_category.lower() in {k.lower() for k in allocations} else args.to_category.strip().title()
    amount = money(args.amount)
    source_amount = money(allocations[source]["amount"])
    if amount > source_amount:
        raise HTTPException(status_code=422, detail=f"{source} only has {plan.currency} {source_amount}")
    if allocations[source].get("locked"):
        raise HTTPException(status_code=422, detail=f"{source} is locked and cannot be reduced without a specialised protected-category workflow")
    allocations[source]["amount"] = str(money(source_amount - amount))
    if target not in allocations:
        allocations[target] = {"category": target, "amount": "0.00", "locked": False, "informational": False}
    allocations[target]["amount"] = str(money(Decimal(allocations[target]["amount"]) + amount))
    proposed = {**before, "allocations": list(allocations.values())}
    proposal = _new_proposal(
        db,
        user=user,
        request=original_request,
        intent="move_budget_allocation",
        before=before,
        proposed=proposed,
        calculation={"from": source, "to": target, "amount": str(amount)},
        conversation_id=conversation_id,
    )
    return {"proposal_id": proposal.id, "before": before, "proposed": proposed, "financial_impact": json.loads(proposal.calculation_json)}


def create_budget_reduction_proposal(
    db: Session, user: User, arguments: dict, *, original_request: str, conversation_id: str | None = None
) -> dict:
    args = ReductionArgs.model_validate(arguments)
    plan = latest_plan(db, user.id)
    if not plan:
        raise HTTPException(status_code=409, detail="Confirm a budget plan before requesting allocation changes")
    before = plan_snapshot(plan)
    allocations = _allocation_map(before)
    category = _resolve_category(allocations, args.category)
    if allocations[category].get("locked"):
        raise HTTPException(status_code=422, detail=f"{category} is locked")
    amount = min(money(args.amount), money(allocations[category]["amount"]))
    allocations[category]["amount"] = str(money(Decimal(allocations[category]["amount"]) - amount))
    remaining_key = _resolve_category(allocations, "Remaining available balance")
    allocations[remaining_key]["amount"] = str(money(Decimal(allocations[remaining_key]["amount"]) + amount))
    proposed = {**before, "allocations": list(allocations.values()), "remaining_balance": allocations[remaining_key]["amount"]}
    proposal = _new_proposal(
        db,
        user=user,
        request=original_request,
        intent="reduce_budget_category",
        before=before,
        proposed=proposed,
        calculation={"category": category, "reduction": str(amount), "released_to": remaining_key},
        conversation_id=conversation_id,
    )
    return {"proposal_id": proposal.id, "before": before, "proposed": proposed, "financial_impact": json.loads(proposal.calculation_json)}


def create_savings_percentage_proposal(
    db: Session, user: User, arguments: dict, *, original_request: str, conversation_id: str | None = None
) -> dict:
    args = SavingsPercentArgs.model_validate(arguments)
    plan = latest_plan(db, user.id)
    if not plan:
        raise HTTPException(status_code=409, detail="Confirm a budget plan before requesting allocation changes")
    before = plan_snapshot(plan)
    allocations = _allocation_map(before)
    savings_key = _resolve_category(allocations, "Normal savings")
    remaining_key = _resolve_category(allocations, "Remaining available balance")
    target = money(plan.total_available * (args.percentage / Decimal("100")))
    current = money(allocations[savings_key]["amount"])
    delta = money(target - current)
    remaining = money(allocations[remaining_key]["amount"])
    if delta > remaining:
        raise HTTPException(status_code=422, detail=f"Only {plan.currency} {remaining} is available without reducing another category")
    allocations[savings_key]["amount"] = str(target)
    allocations[remaining_key]["amount"] = str(money(remaining - delta))
    proposed = {**before, "allocations": list(allocations.values()), "remaining_balance": allocations[remaining_key]["amount"]}
    proposal = _new_proposal(
        db,
        user=user,
        request=original_request,
        intent="set_savings_percentage",
        before=before,
        proposed=proposed,
        calculation={"target_percentage": str(percentage(args.percentage)), "target_amount": str(target), "change": str(delta)},
        conversation_id=conversation_id,
    )
    return {"proposal_id": proposal.id, "before": before, "proposed": proposed, "financial_impact": json.loads(proposal.calculation_json)}


def create_emergency_expense_proposal(
    db: Session, user: User, arguments: dict, *, original_request: str, conversation_id: str | None = None
) -> dict:
    args = EmergencyArgs.model_validate(arguments)
    plan = latest_plan(db, user.id)
    if not plan:
        raise HTTPException(status_code=409, detail="Confirm a budget plan before creating an emergency funding proposal")
    before = plan_snapshot(plan)
    allocations = _allocation_map(before)
    cost = money(args.amount)
    remaining_to_fund = cost
    reductions: list[dict] = []
    funding_order = [
        "Remaining available balance",
        "Online shopping",
        "Planned activities",
        "Smart Wishlist savings",
        "Normal savings",
    ]
    for requested_category in funding_order:
        try:
            category = _resolve_category(allocations, requested_category)
        except HTTPException:
            continue
        available = money(allocations[category]["amount"])
        reduction = min(available, remaining_to_fund)
        if reduction > 0:
            allocations[category]["amount"] = str(money(available - reduction))
            reductions.append({"category": category, "reduction": str(reduction)})
            remaining_to_fund = money(remaining_to_fund - reduction)
        if remaining_to_fund == 0:
            break

    funded_amount = money(cost - remaining_to_fund)
    allocations["Emergency expense"] = {
        "category": "Emergency expense",
        "amount": str(funded_amount),
        "locked": True,
        "informational": False,
    }
    if "Overspending" in allocations:
        allocations["Overspending"]["amount"] = str(remaining_to_fund)
        allocations["Overspending"]["informational"] = True
    proposed = {
        **before,
        "allocations": list(allocations.values()),
        "remaining_balance": allocations.get("Remaining available balance", {}).get("amount", "0.00"),
        "overspending_amount": str(remaining_to_fund),
    }
    calculation = {
        "emergency_cost": str(cost),
        "funded_amount": str(funded_amount),
        "shortfall": str(remaining_to_fund),
        "protected_essentials": args.protect_essentials,
        "reductions": reductions,
        "description": args.description,
    }
    proposal = _new_proposal(
        db,
        user=user,
        request=original_request,
        intent="add_emergency_expense",
        before=before,
        proposed=proposed,
        calculation=calculation,
        conversation_id=conversation_id,
    )
    return {"proposal_id": proposal.id, "before": before, "proposed": proposed, "financial_impact": calculation}


TOOL_FUNCTIONS: dict[str, Callable] = {
    "get_financial_summary": get_financial_summary,
    "calculate_affordability": calculate_affordability,
    "create_budget_transfer_proposal": create_budget_transfer_proposal,
    "create_budget_reduction_proposal": create_budget_reduction_proposal,
    "create_savings_percentage_proposal": create_savings_percentage_proposal,
    "create_emergency_expense_proposal": create_emergency_expense_proposal,
}

TOOL_SCHEMAS = [
    {"name": "get_financial_summary", "mode": "read", "arguments": {}},
    {"name": "calculate_affordability", "mode": "read", "arguments": {"amount": "decimal > 0"}},
    {"name": "create_budget_transfer_proposal", "mode": "proposal", "arguments": {"amount": "decimal > 0", "from_category": "string", "to_category": "string"}},
    {"name": "create_budget_reduction_proposal", "mode": "proposal", "arguments": {"category": "string", "amount": "decimal > 0"}},
    {"name": "create_savings_percentage_proposal", "mode": "proposal", "arguments": {"percentage": "0..100"}},
    {"name": "create_emergency_expense_proposal", "mode": "proposal", "arguments": {"amount": "decimal > 0", "description": "string", "protect_essentials": "boolean"}},
]


def execute_tool(
    name: str,
    *,
    db: Session,
    user: User,
    arguments: dict,
    original_request: str,
    conversation_id: str | None = None,
) -> dict:
    tool = TOOL_FUNCTIONS.get(name)
    if tool is None:
        raise HTTPException(status_code=422, detail="The AI selected a tool that is not on the allowlist")
    try:
        if name.startswith("create_"):
            return tool(db, user, arguments, original_request=original_request, conversation_id=conversation_id)
        return tool(db, user, arguments)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
