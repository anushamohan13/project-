import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.providers import MockAIProvider, get_ai_provider
from app.agents.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, execute_tool
from app.core.config import get_settings
from app.models.entities import (
    AIUsageRecord,
    ChatConversation,
    ChatMessage,
    ChatToolCall,
    ChatToolResult,
    User,
)
from app.services.plans import latest_plan, plan_snapshot

settings = get_settings()


def get_conversation_owned(db: Session, user_id: str, conversation_id: str) -> ChatConversation:
    conversation = db.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Chat conversation not found")
    return conversation


def _ensure_conversation(
    db: Session,
    *,
    user: User,
    conversation_id: str | None,
    mode: str = "ask",
) -> ChatConversation:
    if conversation_id:
        conversation = get_conversation_owned(db, user.id, conversation_id)
        if mode:
            conversation.mode = mode
        return conversation
    conversation = ChatConversation(user_id=user.id, title="Financial assistant", mode=mode)
    db.add(conversation)
    db.flush()
    return conversation


def _context(db: Session, user: User) -> dict:
    profile = user.profile
    plan = latest_plan(db, user.id)
    return {
        "currency": profile.currency if profile else "SGD",
        "current_balance": str(profile.current_balance if profile else 0),
        "latest_plan": plan_snapshot(plan),
        "policy": {
            "read_tools_may_execute": True,
            "change_tools_only_create_proposals": True,
            "essential_categories_protected": True,
        },
    }


def _format_answer(intent: str, result: dict, explanation: str) -> str:
    if intent == "calculate_affordability":
        affordable = result["affordable"]
        answer = (
            f"Current position: {result['currency']} {result['available_balance']} is available. "
            f"Requested purchase: {result['currency']} {result['purchase_cost']}. "
        )
        if affordable:
            return answer + "The purchase fits within the recorded available balance. No saved plan was changed."
        return answer + f"The estimated shortfall is {result['currency']} {result['shortfall']}. No saved plan was changed."
    if intent == "financial_summary":
        return (
            f"Your latest recorded remaining balance is {result['currency']} {result['remaining_balance']}. "
            f"Recorded overspending is {result['currency']} {result['overspending_amount']}."
        )
    if result.get("proposal_id"):
        impact = result.get("financial_impact", {})
        if intent == "add_emergency_expense":
            return (
                f"I prepared an emergency funding proposal. Funded amount: {result['before']['currency']} "
                f"{impact.get('funded_amount', '0.00')}; remaining shortfall: {result['before']['currency']} "
                f"{impact.get('shortfall', '0.00')}. Essential categories were protected. Review the before-and-after allocations and confirm explicitly."
            )
        return f"I prepared a balanced budget-change proposal. {explanation} Review the before-and-after allocations before confirming."
    return explanation


def process_message(
    db: Session,
    *,
    user: User,
    message: str,
    conversation_id: str | None = None,
    mode: str = "ask",
) -> dict:
    conversation = _ensure_conversation(db, user=user, conversation_id=conversation_id, mode=mode)
    user_message = ChatMessage(conversation_id=conversation.id, user_id=user.id, role="user", content=message)
    db.add(user_message)
    db.flush()

    provider = get_ai_provider()
    context = _context(db, user)
    try:
        decision = provider.decide(message=message, context=context, tool_schemas=TOOL_SCHEMAS)
    except Exception as exc:
        if provider.name == "mock":
            raise HTTPException(status_code=502, detail=f"AI provider failed: {str(exc)[:300]}") from exc
        # Deterministic mock fallback preserves availability without bypassing the tool allowlist.
        provider = MockAIProvider()
        decision = provider.decide(message=message, context=context, tool_schemas=TOOL_SCHEMAS)

    if decision.tool_name not in TOOL_FUNCTIONS:
        raise HTTPException(status_code=422, detail="AI provider selected a non-allowlisted tool")
    is_change_tool = decision.tool_name.startswith("create_")
    if mode == "ask" and is_change_tool:
        # Ask mode may preview proposals but never apply them. Proposal creation itself is non-destructive.
        pass

    call = ChatToolCall(
        user_id=user.id,
        conversation_id=conversation.id,
        message_id=user_message.id,
        tool_name=decision.tool_name,
        arguments_json=json.dumps(decision.arguments, sort_keys=True),
        status="running",
    )
    db.add(call)
    db.flush()
    try:
        result = execute_tool(
            decision.tool_name,
            db=db,
            user=user,
            arguments=decision.arguments,
            original_request=message,
            conversation_id=conversation.id,
        )
        call.status = "completed"
        db.add(ChatToolResult(tool_call_id=call.id, result_json=json.dumps(result, default=str, sort_keys=True), success=True))
    except Exception as exc:
        call.status = "failed"
        db.add(ChatToolResult(tool_call_id=call.id, result_json=json.dumps({"error": str(exc)}), success=False))
        db.commit()
        raise

    answer = _format_answer(decision.intent, result, decision.explanation)
    assistant_message = ChatMessage(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        content=answer,
        structured_json=json.dumps({"intent": decision.intent, "tool": decision.tool_name, "result": result}, default=str),
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(AIUsageRecord(user_id=user.id, provider=provider.name, model=settings.ai_model))
    db.commit()

    return {
        "intent": decision.intent,
        "answer": answer,
        "requires_confirmation": bool(result.get("proposal_id")),
        "proposal_id": result.get("proposal_id"),
        "conversation_id": conversation.id,
        "data": result,
    }
