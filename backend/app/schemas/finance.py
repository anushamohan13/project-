from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entities import ActivityPriority, IncomeFrequency, PlanStatus, TransactionKind


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    country: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=3, max_length=100)
    current_balance: Decimal = Field(default=Decimal("0.00"), ge=0)
    normal_savings_percent: Decimal = Field(default=Decimal("20.00"), ge=0, le=100)
    emergency_savings_minimum: Decimal = Field(default=Decimal("0.00"), ge=0)
    savings_before_discretionary: bool = True
    theme_mode: str = Field(default="system", pattern=r"^(light|dark|system)$")
    ai_memory_enabled: bool = True

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ProfileResponse(ORMModel):
    username: str | None
    country: str
    city: str
    currency: str
    timezone: str
    current_balance: Decimal
    normal_savings_percent: Decimal
    emergency_savings_minimum: Decimal
    savings_before_discretionary: bool
    theme_mode: str
    ai_memory_enabled: bool = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str | None = Field(default=None, max_length=80)
    color_token: str | None = Field(default=None, max_length=80)
    is_essential: bool = False
    is_active: bool = True


class CategoryResponse(CategoryCreate, ORMModel):
    id: str
    created_at: datetime


class IncomeStreamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    frequency: IncomeFrequency
    payment_weekday: int | None = Field(default=None, ge=0, le=6)
    payment_day_of_month: int | None = Field(default=None, ge=1, le=31)
    next_payment_date: date
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.frequency == IncomeFrequency.weekly and self.payment_weekday is None:
            raise ValueError("payment_weekday is required for weekly income")
        if self.frequency == IncomeFrequency.monthly and self.payment_day_of_month is None:
            raise ValueError("payment_day_of_month is required for monthly income")
        return self


class IncomeStreamResponse(IncomeStreamCreate, ORMModel):
    id: str


class RecurringExpenseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    frequency: IncomeFrequency
    next_due_date: date
    is_essential: bool = True
    is_active: bool = True
    merchant: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class RecurringExpenseResponse(RecurringExpenseCreate, ORMModel):
    id: str


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    activity_date: date
    city: str | None = Field(default=None, max_length=100)
    people_count: int = Field(default=1, ge=1, le=100)
    estimated_cost: Decimal = Field(ge=0)
    actual_cost: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    manually_entered: bool = True
    recurring: bool = False
    priority: ActivityPriority
    completed: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ActivityResponse(ActivityCreate, ORMModel):
    id: str


class TransactionCreate(BaseModel):
    merchant: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime
    category: str = Field(min_length=1, max_length=80)
    payment_method: str | None = Field(default=None, max_length=80)
    is_online: bool = False
    kind: TransactionKind = TransactionKind.expense
    related_activity_id: str | None = None
    receipt_image_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class TransactionResponse(TransactionCreate, ORMModel):
    id: str
    created_at: datetime


class TransactionSummary(BaseModel):
    currency: str
    total_expenses: Decimal
    total_income: Decimal
    online_spending: Decimal
    by_category: dict[str, Decimal]
    transaction_count: int


class SavingsGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal_type: str = Field(default="normal", pattern=r"^(normal|emergency|other)$")
    target_amount: Decimal = Field(gt=0)
    amount_saved: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(min_length=3, max_length=3)
    target_date: date | None = None
    status: str = Field(default="active", pattern=r"^(active|paused|completed|archived)$")
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class SavingsGoalResponse(SavingsGoalCreate, ORMModel):
    id: str
    progress_percent: Decimal = Decimal("0.00")


class BudgetCalculateRequest(BaseModel):
    period_start: date
    period_end: date
    wishlist_contribution: Decimal = Field(default=Decimal("0.00"), ge=0)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        if (self.period_end - self.period_start).days > 62:
            raise ValueError("planning period cannot exceed 63 days")
        return self


class AllocationResult(BaseModel):
    category: str
    amount: Decimal
    percentage: Decimal
    locked: bool = False
    informational: bool = False


class BudgetResult(BaseModel):
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
    allocations: list[AllocationResult]
    warnings: list[str]


class AllocationInput(ORMModel):
    category: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(ge=0)
    locked: bool = False
    informational: bool = False


class BudgetConfirmRequest(BaseModel):
    period_start: date
    period_end: date
    currency: str = Field(min_length=3, max_length=3)
    total_available: Decimal = Field(ge=0)
    allocations: list[AllocationInput] = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class BudgetPlanResponse(ORMModel):
    id: str
    version: int
    period_start: date
    period_end: date
    currency: str
    total_available: Decimal
    remaining_balance: Decimal
    overspending_amount: Decimal
    status: PlanStatus
    source: str = "manual"
    source_proposal_id: str | None = None
    previous_plan_id: str | None = None
    created_at: datetime
    confirmed_at: datetime | None
    allocations: list[AllocationInput]


class BudgetComparisonItem(BaseModel):
    category: str
    left_amount: Decimal
    right_amount: Decimal
    difference: Decimal
    percent_change: Decimal | None


class BudgetComparisonResponse(BaseModel):
    left_plan: BudgetPlanResponse
    right_plan: BudgetPlanResponse
    total_difference: Decimal
    remaining_difference: Decimal
    allocation_changes: list[BudgetComparisonItem]


class WishlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    category: str = Field(default="Other", max_length=80)
    product_link: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    target_purchase_date: date
    priority: str = Field(default="medium", pattern=r"^(low|medium|high)$")
    amount_saved: Decimal = Field(default=Decimal("0.00"), ge=0)
    automatic_recommendations: bool = True
    status: str = Field(default="active", pattern=r"^(active|paused|completed|archived)$")
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class WishlistResponse(WishlistCreate, ORMModel):
    id: str
    remaining_amount: Decimal
    weeks_remaining: int
    required_weekly_contribution: Decimal
    progress_percent: Decimal


class WishlistContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    contributed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class WishlistContributionResponse(ORMModel):
    id: str
    wishlist_item_id: str
    amount: Decimal
    currency: str
    contributed_at: datetime
    notes: str | None


class WidgetSnapshotResponse(ORMModel):
    plan_id: str | None = None
    plan_version: int = 0
    weekly_allowance: Decimal
    remaining_budget: Decimal
    savings_progress_percent: Decimal
    wishlist_progress_percent: Decimal
    next_salary_date: date | None
    currency: str
    updated_at: datetime


class AuditLogResponse(ORMModel):
    id: str
    action: str
    entity_type: str
    entity_id: str | None
    detail_json: str | None
    created_at: datetime

class CurrencyRateCreate(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=0)
    source: str = Field(min_length=1, max_length=120)
    retrieved_at: datetime

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def uppercase_rate_currency(cls, value: str) -> str:
        return value.upper()


class CurrencyRateResponse(CurrencyRateCreate, ORMModel):
    id: str


class AIRecommendationCreate(BaseModel):
    recommendation_type: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=500)
    detail_json: str = Field(min_length=2, max_length=20000)
    status: str = Field(default="active", pattern=r"^(active|accepted|dismissed|archived)$")


class AIRecommendationResponse(AIRecommendationCreate, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class ConfirmedCostMemoryCreate(BaseModel):
    activity_name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    city: str | None = Field(default=None, max_length=100)
    people_count: int = Field(default=1, ge=1, le=100)
    confirmed_amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    confirmed_at: datetime | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_memory_currency(cls, value: str) -> str:
        return value.upper()


class ConfirmedCostMemoryResponse(ConfirmedCostMemoryCreate, ORMModel):
    id: str
    confirmed_at: datetime
