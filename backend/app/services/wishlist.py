from datetime import date
from decimal import Decimal, ROUND_CEILING

from app.schemas.common import money, percentage


def calculate_wishlist_progress(price: Decimal, amount_saved: Decimal, target_date: date, today: date | None = None) -> dict:
    today = today or date.today()
    remaining = money(max(Decimal("0.00"), price - amount_saved))
    days_remaining = max(0, (target_date - today).days)
    weeks_remaining = max(1, int((Decimal(days_remaining) / Decimal("7")).to_integral_value(rounding=ROUND_CEILING)))
    required_weekly = money(remaining / Decimal(weeks_remaining)) if remaining > 0 else Decimal("0.00")
    progress = percentage(min(Decimal("100"), (amount_saved / price) * Decimal("100"))) if price > 0 else Decimal("0.00")
    return {
        "remaining_amount": remaining,
        "weeks_remaining": weeks_remaining,
        "required_weekly_contribution": required_weekly,
        "progress_percent": progress,
    }
