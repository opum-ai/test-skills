"""Money helpers. Every amount in the shop is a Decimal in the store currency."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    """Raised when a value cannot be used as a money amount."""


def to_money(value) -> Decimal:
    """Convert an int, str, float or Decimal to a Decimal amount.

    Floats go through their string form so that 0.1 becomes Decimal("0.1"), not the
    binary approximation.
    """
    if isinstance(value, bool):
        raise MoneyError("booleans are not money")
    try:
        amount = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except InvalidOperation:
        raise MoneyError(f"not a money amount: {value!r}") from None
    if not amount.is_finite():
        raise MoneyError(f"not a finite amount: {value!r}")
    return amount


def _round_cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def round_cents(value) -> Decimal:
    """Round to whole cents, half away from zero (0.125 -> 0.13)."""
    return _round_cents(to_money(value))
