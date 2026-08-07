from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Transaction, TransactionKind
from app.schemas.common import money


def transaction_summary(
    db: Session,
    *,
    user_id: str,
    currency: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    query = select(Transaction).where(Transaction.user_id == user_id)
    if start:
        query = query.where(Transaction.occurred_at >= start)
    if end:
        query = query.where(Transaction.occurred_at <= end)
    transactions = db.scalars(query.order_by(Transaction.occurred_at.desc())).all()

    total_expenses = Decimal("0.00")
    total_income = Decimal("0.00")
    online_spending = Decimal("0.00")
    by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for item in transactions:
        if item.currency != currency:
            continue
        if item.kind == TransactionKind.expense:
            total_expenses += item.amount
            by_category[item.category] += item.amount
            if item.is_online:
                online_spending += item.amount
        else:
            total_income += item.amount
    return {
        "currency": currency,
        "total_expenses": money(total_expenses),
        "total_income": money(total_income),
        "online_spending": money(online_spending),
        "by_category": {key: money(value) for key, value in sorted(by_category.items())},
        "transaction_count": len(transactions),
    }
