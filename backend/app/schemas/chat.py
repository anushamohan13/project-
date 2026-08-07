from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import ProposalStatus
from app.schemas.finance import AllocationInput, BudgetPlanResponse


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: str = Field(default="Financial assistant", min_length=1, max_length=160)
    mode: str = Field(default="ask", pattern=r"^(ask|action)$")


class ConversationResponse(ORMModel):
    id: str
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: str | None = Field(default=None, pattern=r"^(ask|action)$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    intent: str
    answer: str
    requires_confirmation: bool = False
    proposal_id: str | None = None
    conversation_id: str | None = None
    data: dict = Field(default_factory=dict)


class ProposalResponse(BaseModel):
    id: str
    status: ProposalStatus
    original_request: str
    interpreted_intent: str
    base_plan_id: str | None
    base_plan_version: int | None
    before_allocations: list[AllocationInput]
    proposed_allocations: list[AllocationInput]
    financial_impact: dict
    expires_at: datetime
    created_at: datetime
    applied_plan_id: str | None
    reversal_plan_id: str | None


class ProposalActionResponse(BaseModel):
    proposal: ProposalResponse
    plan: BudgetPlanResponse | None = None


class MemoryCreate(BaseModel):
    memory_key: str = Field(min_length=1, max_length=100)
    memory_value: str = Field(min_length=1, max_length=4000)
    consented: bool = True


class MemoryResponse(MemoryCreate, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime
