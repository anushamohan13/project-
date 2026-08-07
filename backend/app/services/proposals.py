import json
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FinancialChangeProposal, ProposalStatus, User
from app.schemas.chat import ProposalResponse
from app.services.audit import record_audit
from app.services.plans import allocations_from_snapshot, create_confirmed_plan, latest_plan


def get_proposal_owned(db: Session, user_id: str, proposal_id: str) -> FinancialChangeProposal:
    proposal = db.scalar(
        select(FinancialChangeProposal).where(
            FinancialChangeProposal.id == proposal_id,
            FinancialChangeProposal.user_id == user_id,
        )
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Financial change proposal not found")
    return proposal


def proposal_response(proposal: FinancialChangeProposal) -> ProposalResponse:
    before = json.loads(proposal.before_plan_json)
    proposed = json.loads(proposal.proposed_plan_json)
    calculation = json.loads(proposal.calculation_json)
    return ProposalResponse(
        id=proposal.id,
        status=proposal.status,
        original_request=proposal.original_request,
        interpreted_intent=proposal.interpreted_intent,
        base_plan_id=proposal.base_plan_id,
        base_plan_version=proposal.base_plan_version,
        before_allocations=before.get("allocations", []),
        proposed_allocations=proposed.get("allocations", []),
        financial_impact=calculation,
        expires_at=proposal.expires_at,
        created_at=proposal.created_at,
        applied_plan_id=proposal.applied_plan_id,
        reversal_plan_id=proposal.reversal_plan_id,
    )


def _parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def confirm_proposal(db: Session, *, user: User, proposal: FinancialChangeProposal):
    now = datetime.now(timezone.utc)
    if proposal.status == ProposalStatus.applied:
        raise HTTPException(status_code=409, detail="Proposal has already been applied")
    if proposal.status not in {ProposalStatus.awaiting_confirmation, ProposalStatus.confirmed}:
        raise HTTPException(status_code=409, detail=f"Proposal cannot be confirmed from status {proposal.status.value}")
    if _aware(proposal.expires_at) <= now:
        proposal.status = ProposalStatus.expired
        db.commit()
        raise HTTPException(status_code=409, detail="Proposal has expired; recalculate it using the latest plan")

    current = latest_plan(db, user.id)
    if proposal.base_plan_version is not None and (current is None or current.version != proposal.base_plan_version):
        raise HTTPException(status_code=409, detail="The underlying budget changed; recalculate this proposal")

    proposed = json.loads(proposal.proposed_plan_json)
    proposal.status = ProposalStatus.confirmed
    proposal.confirmed_at = now
    plan = create_confirmed_plan(
        db,
        user=user,
        period_start=_parse_date(proposed["period_start"]),
        period_end=_parse_date(proposed["period_end"]),
        currency=proposed["currency"],
        total_available=proposed["total_available"],
        allocations=allocations_from_snapshot(proposed),
        source="ai",
        source_proposal_id=proposal.id,
        previous_plan_id=current.id if current else None,
    )
    proposal.status = ProposalStatus.applied
    proposal.applied_plan_id = plan.id
    proposal.applied_at = now
    record_audit(
        db,
        user_id=user.id,
        action="financial_change_proposal.applied",
        entity_type="FinancialChangeProposal",
        entity_id=proposal.id,
        detail={"plan_id": plan.id, "plan_version": plan.version},
    )
    db.commit()
    db.refresh(plan)
    return plan


def reject_proposal(db: Session, *, user: User, proposal: FinancialChangeProposal) -> None:
    if proposal.status not in {ProposalStatus.draft, ProposalStatus.awaiting_confirmation, ProposalStatus.confirmed}:
        raise HTTPException(status_code=409, detail="Proposal cannot be rejected in its current status")
    proposal.status = ProposalStatus.rejected
    record_audit(
        db,
        user_id=user.id,
        action="financial_change_proposal.rejected",
        entity_type="FinancialChangeProposal",
        entity_id=proposal.id,
    )
    db.commit()


def reverse_proposal(db: Session, *, user: User, proposal: FinancialChangeProposal):
    if proposal.status != ProposalStatus.applied or not proposal.applied_plan_id:
        raise HTTPException(status_code=409, detail="Only an applied proposal can be reversed")
    current = latest_plan(db, user.id)
    if current is None or current.id != proposal.applied_plan_id:
        raise HTTPException(status_code=409, detail="Only the latest eligible AI change can be reversed safely")

    before = json.loads(proposal.before_plan_json)
    plan = create_confirmed_plan(
        db,
        user=user,
        period_start=_parse_date(before["period_start"]),
        period_end=_parse_date(before["period_end"]),
        currency=before["currency"],
        total_available=before["total_available"],
        allocations=allocations_from_snapshot(before),
        source="reversal",
        source_proposal_id=proposal.id,
        previous_plan_id=current.id,
    )
    proposal.status = ProposalStatus.reversed
    proposal.reversal_plan_id = plan.id
    proposal.reversed_at = datetime.now(timezone.utc)
    record_audit(
        db,
        user_id=user.id,
        action="financial_change_proposal.reversed",
        entity_type="FinancialChangeProposal",
        entity_id=proposal.id,
        detail={"reversal_plan_id": plan.id, "plan_version": plan.version},
    )
    db.commit()
    db.refresh(plan)
    return plan
