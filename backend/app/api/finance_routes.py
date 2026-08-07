from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.entities import (
    AIRecommendation,
    Activity,
    AuditLog,
    BudgetPlan,
    ConfirmedCostMemory,
    CurrencyRate,
    CustomCategory,
    IncomeStream,
    RecurringExpense,
    SavingsGoal,
    PlanStatus,
    Transaction,
    User,
    UserProfile,
    WidgetSnapshot,
    WishlistContribution,
    WishlistItem,
)
from app.schemas.common import money, percentage
from app.schemas.finance import (
    AIRecommendationCreate,
    AIRecommendationResponse,
    ActivityCreate,
    ActivityResponse,
    AllocationResult,
    AuditLogResponse,
    BudgetCalculateRequest,
    BudgetComparisonResponse,
    BudgetConfirmRequest,
    BudgetPlanResponse,
    BudgetResult,
    CategoryCreate,
    CategoryResponse,
    ConfirmedCostMemoryCreate,
    ConfirmedCostMemoryResponse,
    CurrencyRateCreate,
    CurrencyRateResponse,
    IncomeStreamCreate,
    IncomeStreamResponse,
    ProfileResponse,
    ProfileUpdate,
    RecurringExpenseCreate,
    RecurringExpenseResponse,
    SavingsGoalCreate,
    SavingsGoalResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionSummary,
    WidgetSnapshotResponse,
    WishlistContributionCreate,
    WishlistContributionResponse,
    WishlistCreate,
    WishlistResponse,
)
from app.services.audit import record_audit
from app.services.budgeting import allocation_percent, calculate_budget
from app.services.plans import compare_plans, create_confirmed_plan, get_plan_owned, latest_plan
from app.services.transactions import transaction_summary
from app.services.wishlist import calculate_wishlist_progress

router = APIRouter(tags=["finance"])


def _owned(db: Session, model, entity_id: str, user_id: str, label: str):
    entity = db.scalar(select(model).where(model.id == entity_id, model.user_id == user_id))
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return entity


def _commit_integrity(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


def _profile_response(user: User) -> ProfileResponse:
    profile = user.profile or UserProfile(user_id=user.id)
    return ProfileResponse(
        username=user.username,
        country=profile.country,
        city=profile.city,
        currency=profile.currency,
        timezone=profile.timezone,
        current_balance=profile.current_balance,
        normal_savings_percent=profile.normal_savings_percent,
        emergency_savings_minimum=profile.emergency_savings_minimum,
        savings_before_discretionary=profile.savings_before_discretionary,
        theme_mode=profile.theme_mode,
        ai_memory_enabled=profile.ai_memory_enabled,
    )


def _wishlist_response(item: WishlistItem) -> WishlistResponse:
    calculations = calculate_wishlist_progress(item.price, item.amount_saved, item.target_purchase_date)
    return WishlistResponse.model_validate(
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "category": item.category,
            "product_link": item.product_link,
            "image_url": item.image_url,
            "price": item.price,
            "currency": item.currency,
            "target_purchase_date": item.target_purchase_date,
            "priority": item.priority,
            "amount_saved": item.amount_saved,
            "automatic_recommendations": item.automatic_recommendations,
            "status": item.status,
            "notes": item.notes,
            **calculations,
        }
    )


def _savings_goal_response(item: SavingsGoal) -> SavingsGoalResponse:
    progress = percentage((item.amount_saved / item.target_amount) * 100) if item.target_amount > 0 else Decimal("0.00")
    return SavingsGoalResponse.model_validate(
        {
            "id": item.id,
            "name": item.name,
            "goal_type": item.goal_type,
            "target_amount": item.target_amount,
            "amount_saved": item.amount_saved,
            "currency": item.currency,
            "target_date": item.target_date,
            "status": item.status,
            "notes": item.notes,
            "progress_percent": min(progress, Decimal("100.00")),
        }
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 2}


@router.get("/profile", response_model=ProfileResponse)
def get_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return _profile_response(user)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    existing_username = db.scalar(select(User).where(User.username == payload.username, User.id != user.id))
    if existing_username:
        raise HTTPException(status_code=409, detail="Username is already in use")
    user.username = payload.username
    if user.profile is None:
        user.profile = UserProfile()
    for key, value in payload.model_dump(exclude={"username"}).items():
        setattr(user.profile, key, value)
    record_audit(db, user_id=user.id, action="profile.updated", entity_type="UserProfile", entity_id=user.profile.id)
    db.commit()
    db.refresh(user)
    return _profile_response(user)


# ---------- Custom categories ----------
@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(CustomCategory).where(CustomCategory.user_id == user.id).order_by(CustomCategory.name)).all()


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(payload: CategoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = CustomCategory(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="category.created", entity_type="CustomCategory", entity_id=item.id)
    _commit_integrity(db, "A category with this name already exists")
    db.refresh(item)
    return item


@router.get("/categories/{entity_id}", response_model=CategoryResponse)
def get_category(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, CustomCategory, entity_id, user.id, "Category")


@router.put("/categories/{entity_id}", response_model=CategoryResponse)
def update_category(entity_id: str, payload: CategoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, CustomCategory, entity_id, user.id, "Category")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="category.updated", entity_type="CustomCategory", entity_id=item.id)
    _commit_integrity(db, "A category with this name already exists")
    db.refresh(item)
    return item


@router.delete("/categories/{entity_id}", status_code=204)
def delete_category(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, CustomCategory, entity_id, user.id, "Category")
    record_audit(db, user_id=user.id, action="category.deleted", entity_type="CustomCategory", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Income streams ----------
@router.get("/income-streams", response_model=list[IncomeStreamResponse])
def list_income_streams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(IncomeStream).where(IncomeStream.user_id == user.id).order_by(IncomeStream.name)).all()


@router.post("/income-streams", response_model=IncomeStreamResponse, status_code=201)
def create_income_stream(payload: IncomeStreamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = IncomeStream(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="income.created", entity_type="IncomeStream", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/income-streams/{entity_id}", response_model=IncomeStreamResponse)
def get_income_stream(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, IncomeStream, entity_id, user.id, "Income stream")


@router.put("/income-streams/{entity_id}", response_model=IncomeStreamResponse)
def update_income_stream(entity_id: str, payload: IncomeStreamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, IncomeStream, entity_id, user.id, "Income stream")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="income.updated", entity_type="IncomeStream", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/income-streams/{entity_id}", status_code=204)
def delete_income_stream(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, IncomeStream, entity_id, user.id, "Income stream")
    record_audit(db, user_id=user.id, action="income.deleted", entity_type="IncomeStream", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Recurring expenses ----------
@router.get("/recurring-expenses", response_model=list[RecurringExpenseResponse])
def list_recurring_expenses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id).order_by(RecurringExpense.next_due_date)).all()


@router.post("/recurring-expenses", response_model=RecurringExpenseResponse, status_code=201)
def create_recurring_expense(payload: RecurringExpenseCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = RecurringExpense(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="recurring_expense.created", entity_type="RecurringExpense", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/recurring-expenses/{entity_id}", response_model=RecurringExpenseResponse)
def get_recurring_expense(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, RecurringExpense, entity_id, user.id, "Recurring expense")


@router.put("/recurring-expenses/{entity_id}", response_model=RecurringExpenseResponse)
def update_recurring_expense(entity_id: str, payload: RecurringExpenseCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, RecurringExpense, entity_id, user.id, "Recurring expense")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="recurring_expense.updated", entity_type="RecurringExpense", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/recurring-expenses/{entity_id}", status_code=204)
def delete_recurring_expense(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, RecurringExpense, entity_id, user.id, "Recurring expense")
    record_audit(db, user_id=user.id, action="recurring_expense.deleted", entity_type="RecurringExpense", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Activities ----------
@router.get("/activities", response_model=list[ActivityResponse])
def list_activities(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Activity).where(Activity.user_id == user.id)
    if start:
        query = query.where(Activity.activity_date >= start)
    if end:
        query = query.where(Activity.activity_date <= end)
    return db.scalars(query.order_by(Activity.activity_date)).all()


@router.post("/activities", response_model=ActivityResponse, status_code=201)
def create_activity(payload: ActivityCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = Activity(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="activity.created", entity_type="Activity", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/activities/{entity_id}", response_model=ActivityResponse)
def get_activity(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, Activity, entity_id, user.id, "Activity")


@router.put("/activities/{entity_id}", response_model=ActivityResponse)
def update_activity(entity_id: str, payload: ActivityCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, Activity, entity_id, user.id, "Activity")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="activity.updated", entity_type="Activity", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/activities/{entity_id}", status_code=204)
def delete_activity(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, Activity, entity_id, user.id, "Activity")
    record_audit(db, user_id=user.id, action="activity.deleted", entity_type="Activity", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Transactions ----------
@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    category: str | None = Query(default=None),
    online_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Transaction).where(Transaction.user_id == user.id)
    if start:
        query = query.where(Transaction.occurred_at >= start)
    if end:
        query = query.where(Transaction.occurred_at <= end)
    if category:
        query = query.where(Transaction.category == category)
    if online_only:
        query = query.where(Transaction.is_online.is_(True))
    return db.scalars(query.order_by(Transaction.occurred_at.desc())).all()


@router.post("/transactions", response_model=TransactionResponse, status_code=201)
def create_transaction(payload: TransactionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.related_activity_id:
        _owned(db, Activity, payload.related_activity_id, user.id, "Related activity")
    item = Transaction(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="transaction.created", entity_type="Transaction", entity_id=item.id, detail={"category": item.category})
    db.commit()
    db.refresh(item)
    return item


@router.get("/transactions/summary", response_model=TransactionSummary)
def get_transaction_summary(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    currency = user.profile.currency if user.profile else "SGD"
    return transaction_summary(db, user_id=user.id, currency=currency, start=start, end=end)


@router.get("/transactions/{entity_id}", response_model=TransactionResponse)
def get_transaction(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, Transaction, entity_id, user.id, "Transaction")


@router.put("/transactions/{entity_id}", response_model=TransactionResponse)
def update_transaction(entity_id: str, payload: TransactionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, Transaction, entity_id, user.id, "Transaction")
    if payload.related_activity_id:
        _owned(db, Activity, payload.related_activity_id, user.id, "Related activity")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="transaction.updated", entity_type="Transaction", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/transactions/{entity_id}", status_code=204)
def delete_transaction(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, Transaction, entity_id, user.id, "Transaction")
    record_audit(db, user_id=user.id, action="transaction.deleted", entity_type="Transaction", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Savings goals ----------
@router.get("/savings-goals", response_model=list[SavingsGoalResponse])
def list_savings_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.name)).all()
    return [_savings_goal_response(item) for item in items]


@router.post("/savings-goals", response_model=SavingsGoalResponse, status_code=201)
def create_savings_goal(payload: SavingsGoalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = SavingsGoal(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="savings_goal.created", entity_type="SavingsGoal", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return _savings_goal_response(item)


@router.get("/savings-goals/{entity_id}", response_model=SavingsGoalResponse)
def get_savings_goal(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _savings_goal_response(_owned(db, SavingsGoal, entity_id, user.id, "Savings goal"))


@router.put("/savings-goals/{entity_id}", response_model=SavingsGoalResponse)
def update_savings_goal(entity_id: str, payload: SavingsGoalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, SavingsGoal, entity_id, user.id, "Savings goal")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="savings_goal.updated", entity_type="SavingsGoal", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return _savings_goal_response(item)


@router.delete("/savings-goals/{entity_id}", status_code=204)
def delete_savings_goal(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, SavingsGoal, entity_id, user.id, "Savings goal")
    record_audit(db, user_id=user.id, action="savings_goal.deleted", entity_type="SavingsGoal", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Wishlist and contributions ----------
@router.get("/wishlist", response_model=list[WishlistResponse])
def list_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(WishlistItem).where(WishlistItem.user_id == user.id).order_by(WishlistItem.target_purchase_date)).all()
    return [_wishlist_response(item) for item in items]


@router.post("/wishlist", response_model=WishlistResponse, status_code=201)
def create_wishlist(payload: WishlistCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = WishlistItem(user_id=user.id, **payload.model_dump())
    db.add(item)
    record_audit(db, user_id=user.id, action="wishlist.created", entity_type="WishlistItem", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return _wishlist_response(item)


@router.get("/wishlist/{entity_id}", response_model=WishlistResponse)
def get_wishlist(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _wishlist_response(_owned(db, WishlistItem, entity_id, user.id, "Wishlist item"))


@router.put("/wishlist/{entity_id}", response_model=WishlistResponse)
def update_wishlist(entity_id: str, payload: WishlistCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="wishlist.updated", entity_type="WishlistItem", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return _wishlist_response(item)


@router.delete("/wishlist/{entity_id}", status_code=204)
def delete_wishlist(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    record_audit(db, user_id=user.id, action="wishlist.deleted", entity_type="WishlistItem", entity_id=item.id)
    db.delete(item)
    db.commit()


@router.get("/wishlist/{entity_id}/contributions", response_model=list[WishlistContributionResponse])
def list_wishlist_contributions(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    return db.scalars(
        select(WishlistContribution)
        .where(WishlistContribution.user_id == user.id, WishlistContribution.wishlist_item_id == entity_id)
        .order_by(WishlistContribution.contributed_at.desc())
    ).all()


@router.post("/wishlist/{entity_id}/contributions", response_model=WishlistContributionResponse, status_code=201)
def create_wishlist_contribution(entity_id: str, payload: WishlistContributionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist = _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    if payload.currency != wishlist.currency:
        raise HTTPException(status_code=422, detail="Contribution currency must match the wishlist item until verified FX is configured")
    item = WishlistContribution(
        user_id=user.id,
        wishlist_item_id=wishlist.id,
        amount=payload.amount,
        currency=payload.currency,
        contributed_at=payload.contributed_at or datetime.now(timezone.utc),
        notes=payload.notes,
    )
    wishlist.amount_saved = money(wishlist.amount_saved + payload.amount)
    db.add(item)
    record_audit(db, user_id=user.id, action="wishlist_contribution.created", entity_type="WishlistContribution", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.put("/wishlist/{entity_id}/contributions/{contribution_id}", response_model=WishlistContributionResponse)
def update_wishlist_contribution(entity_id: str, contribution_id: str, payload: WishlistContributionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist = _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    item = db.scalar(select(WishlistContribution).where(WishlistContribution.id == contribution_id, WishlistContribution.user_id == user.id, WishlistContribution.wishlist_item_id == entity_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Wishlist contribution not found")
    if payload.currency != wishlist.currency:
        raise HTTPException(status_code=422, detail="Contribution currency must match the wishlist item")
    difference = money(payload.amount - item.amount)
    wishlist.amount_saved = money(max(Decimal("0.00"), wishlist.amount_saved + difference))
    item.amount = payload.amount
    item.currency = payload.currency
    item.contributed_at = payload.contributed_at or item.contributed_at
    item.notes = payload.notes
    record_audit(db, user_id=user.id, action="wishlist_contribution.updated", entity_type="WishlistContribution", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/wishlist/{entity_id}/contributions/{contribution_id}", status_code=204)
def delete_wishlist_contribution(entity_id: str, contribution_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist = _owned(db, WishlistItem, entity_id, user.id, "Wishlist item")
    item = db.scalar(select(WishlistContribution).where(WishlistContribution.id == contribution_id, WishlistContribution.user_id == user.id, WishlistContribution.wishlist_item_id == entity_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Wishlist contribution not found")
    wishlist.amount_saved = money(max(Decimal("0.00"), wishlist.amount_saved - item.amount))
    record_audit(db, user_id=user.id, action="wishlist_contribution.deleted", entity_type="WishlistContribution", entity_id=item.id)
    db.delete(item)
    db.commit()


# ---------- Budget calculation and immutable plan history ----------
@router.post("/budgets/calculate", response_model=BudgetResult)
def calculate_budget_route(payload: BudgetCalculateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.profile is None:
        raise HTTPException(status_code=400, detail="Complete profile before calculating a budget")
    incomes = db.scalars(select(IncomeStream).where(IncomeStream.user_id == user.id, IncomeStream.is_active.is_(True))).all()
    activities = db.scalars(select(Activity).where(Activity.user_id == user.id, Activity.activity_date >= payload.period_start, Activity.activity_date <= payload.period_end)).all()
    expenses = db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id, RecurringExpense.is_active.is_(True))).all()
    try:
        result = calculate_budget(
            period_start=payload.period_start,
            period_end=payload.period_end,
            planning_currency=user.profile.currency,
            current_balance=user.profile.current_balance,
            savings_percent=user.profile.normal_savings_percent,
            incomes=incomes,
            activities=activities,
            recurring_expenses=expenses,
            wishlist_contribution=payload.wishlist_contribution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BudgetResult(
        period_start=result.period_start,
        period_end=result.period_end,
        currency=result.currency,
        income_for_period=result.income_for_period,
        current_balance=result.current_balance,
        total_available=result.total_available,
        remaining_balance=result.remaining_balance,
        overspending_amount=result.overspending_amount,
        projected_balance_before_next_salary=result.projected_balance_before_next_salary,
        required_reduction=result.required_reduction,
        allocations=[AllocationResult(category=item.category, amount=item.amount, percentage=allocation_percent(item.amount, result.total_available), locked=item.locked, informational=item.informational) for item in result.allocations],
        warnings=list(result.warnings),
    )


@router.post("/budgets/confirm", response_model=BudgetPlanResponse, status_code=201)
def confirm_budget(payload: BudgetConfirmRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current = latest_plan(db, user.id)
    plan = create_confirmed_plan(
        db,
        user=user,
        period_start=payload.period_start,
        period_end=payload.period_end,
        currency=payload.currency,
        total_available=payload.total_available,
        allocations=payload.allocations,
        source="manual",
        previous_plan_id=current.id if current else None,
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/budgets/latest", response_model=BudgetPlanResponse)
def get_latest_budget(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = latest_plan(db, user.id)
    if plan is None:
        raise HTTPException(status_code=404, detail="No confirmed budget plan found")
    return plan


@router.get("/budgets/history", response_model=list[BudgetPlanResponse])
def budget_history(limit: int = Query(default=20, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(BudgetPlan).options(selectinload(BudgetPlan.allocations)).where(BudgetPlan.user_id == user.id).order_by(BudgetPlan.version.desc()).limit(limit)).all()


@router.get("/budgets/compare", response_model=BudgetComparisonResponse)
def compare_budget_versions(left_id: str, right_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    left = get_plan_owned(db, user.id, left_id)
    right = get_plan_owned(db, user.id, right_id)
    total_difference, remaining_difference, changes = compare_plans(left, right)
    return BudgetComparisonResponse(left_plan=left, right_plan=right, total_difference=total_difference, remaining_difference=remaining_difference, allocation_changes=changes)


@router.get("/budgets/{plan_id}", response_model=BudgetPlanResponse)
def get_budget_plan(plan_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_plan_owned(db, user.id, plan_id)


@router.post("/budgets/{plan_id}/archive", response_model=BudgetPlanResponse)
def archive_budget_plan(plan_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = get_plan_owned(db, user.id, plan_id)
    plan.status = PlanStatus.archived
    record_audit(db, user_id=user.id, action="budget_plan.archived", entity_type="BudgetPlan", entity_id=plan.id)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/widget/snapshot", response_model=WidgetSnapshotResponse)
def widget_snapshot(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    snapshot = db.scalar(select(WidgetSnapshot).where(WidgetSnapshot.user_id == user.id))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Confirm a budget plan to create widget data")
    return snapshot


# ---------- Verified-data records and AI output records ----------
@router.get("/currency-rates", response_model=list[CurrencyRateResponse])
def list_currency_rates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(CurrencyRate).where(CurrencyRate.user_id == user.id).order_by(CurrencyRate.retrieved_at.desc())).all()


@router.post("/currency-rates", response_model=CurrencyRateResponse, status_code=201)
def create_currency_rate(payload: CurrencyRateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = CurrencyRate(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/currency-rates/{entity_id}", response_model=CurrencyRateResponse)
def get_currency_rate(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, CurrencyRate, entity_id, user.id, "Currency rate")


@router.put("/currency-rates/{entity_id}", response_model=CurrencyRateResponse)
def update_currency_rate(entity_id: str, payload: CurrencyRateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, CurrencyRate, entity_id, user.id, "Currency rate")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/currency-rates/{entity_id}", status_code=204)
def delete_currency_rate(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, CurrencyRate, entity_id, user.id, "Currency rate"))
    db.commit()


@router.get("/ai-recommendations", response_model=list[AIRecommendationResponse])
def list_ai_recommendations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(AIRecommendation).where(AIRecommendation.user_id == user.id).order_by(AIRecommendation.created_at.desc())).all()


@router.post("/ai-recommendations", response_model=AIRecommendationResponse, status_code=201)
def create_ai_recommendation(payload: AIRecommendationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = AIRecommendation(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/ai-recommendations/{entity_id}", response_model=AIRecommendationResponse)
def get_ai_recommendation(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, AIRecommendation, entity_id, user.id, "AI recommendation")


@router.put("/ai-recommendations/{entity_id}", response_model=AIRecommendationResponse)
def update_ai_recommendation(entity_id: str, payload: AIRecommendationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, AIRecommendation, entity_id, user.id, "AI recommendation")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/ai-recommendations/{entity_id}", status_code=204)
def delete_ai_recommendation(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, AIRecommendation, entity_id, user.id, "AI recommendation"))
    db.commit()


@router.get("/confirmed-cost-memories", response_model=list[ConfirmedCostMemoryResponse])
def list_confirmed_cost_memories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(ConfirmedCostMemory).where(ConfirmedCostMemory.user_id == user.id).order_by(ConfirmedCostMemory.confirmed_at.desc())).all()


@router.post("/confirmed-cost-memories", response_model=ConfirmedCostMemoryResponse, status_code=201)
def create_confirmed_cost_memory(payload: ConfirmedCostMemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["confirmed_at"] = data["confirmed_at"] or datetime.now(timezone.utc)
    item = ConfirmedCostMemory(user_id=user.id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/confirmed-cost-memories/{entity_id}", response_model=ConfirmedCostMemoryResponse)
def get_confirmed_cost_memory(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, ConfirmedCostMemory, entity_id, user.id, "Confirmed cost memory")


@router.put("/confirmed-cost-memories/{entity_id}", response_model=ConfirmedCostMemoryResponse)
def update_confirmed_cost_memory(entity_id: str, payload: ConfirmedCostMemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _owned(db, ConfirmedCostMemory, entity_id, user.id, "Confirmed cost memory")
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/confirmed-cost-memories/{entity_id}", status_code=204)
def delete_confirmed_cost_memory(entity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, ConfirmedCostMemory, entity_id, user.id, "Confirmed cost memory"))
    db.commit()


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(limit: int = Query(default=100, ge=1, le=500), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(limit)).all()
