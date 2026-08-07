from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def percentage(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)
