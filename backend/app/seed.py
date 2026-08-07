from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models.entities import (
    Activity,
    ActivityPriority,
    CustomCategory,
    IncomeFrequency,
    IncomeStream,
    NotificationPreference,
    Transaction,
    TransactionKind,
    User,
    UserProfile,
    WishlistItem,
)


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@example.com"))
        if user is not None:
            print("Demo data already exists")
            return

        user = User(email="demo@example.com", username="demo_user")
        user.profile = UserProfile(
            country="Singapore",
            city="Singapore",
            currency="SGD",
            timezone="Asia/Singapore",
            current_balance=Decimal("500.00"),
            normal_savings_percent=Decimal("20.00"),
        )
        db.add(user)
        db.flush()
        db.add_all(
            [
                CustomCategory(user_id=user.id, name="Pets", icon="pawprint", color_token="orange"),
                IncomeStream(
                    user_id=user.id,
                    name="Main Salary",
                    amount=Decimal("1500.00"),
                    currency="SGD",
                    frequency=IncomeFrequency.weekly,
                    payment_weekday=date.today().weekday(),
                    next_payment_date=date.today(),
                    is_active=True,
                ),
                Activity(
                    user_id=user.id,
                    name="Groceries",
                    category="Groceries",
                    activity_date=date.today() + timedelta(days=1),
                    city="Singapore",
                    people_count=2,
                    estimated_cost=Decimal("180.00"),
                    currency="SGD",
                    manually_entered=True,
                    recurring=False,
                    priority=ActivityPriority.essential,
                ),
                Transaction(
                    user_id=user.id,
                    merchant="Demo supermarket",
                    amount=Decimal("42.50"),
                    currency="SGD",
                    occurred_at=datetime.now(timezone.utc),
                    category="Groceries",
                    payment_method="Card",
                    is_online=False,
                    kind=TransactionKind.expense,
                ),
                WishlistItem(
                    user_id=user.id,
                    name="New laptop",
                    category="Technology",
                    price=Decimal("1500.00"),
                    currency="SGD",
                    target_purchase_date=date.today() + timedelta(days=120),
                    priority="high",
                    amount_saved=Decimal("200.00"),
                    automatic_recommendations=True,
                ),
                NotificationPreference(user_id=user.id, timezone="Asia/Singapore"),
            ]
        )
        db.commit()
        print("Created demo@example.com Phase 2 seed data")


if __name__ == "__main__":
    seed()
