"""Line pricing: unit price times quantity, less a volume discount for large orders."""
from decimal import Decimal

from .money import _round_cents, to_money

# (minimum quantity, discount rate), checked from the largest tier down.
VOLUME_TIERS = (
    (100, Decimal("0.15")),
    (50, Decimal("0.10")),
    (10, Decimal("0.05")),
)
MAX_QTY = 999


class PricingError(ValueError):
    """Raised for an invalid price or quantity."""


def volume_discount_rate(qty: int) -> Decimal:
    """The volume discount rate for a line of `qty` units."""
    for min_qty, rate in VOLUME_TIERS:
        if qty >= min_qty:
            return rate
    return Decimal("0")


def _validate(unit_price, qty) -> Decimal:
    if not isinstance(qty, int) or isinstance(qty, bool):
        raise PricingError("quantity must be a whole number")
    if qty <= 0:
        raise PricingError("quantity must be positive")
    if qty > MAX_QTY:
        raise PricingError(f"quantity cannot exceed {MAX_QTY}")
    price = to_money(unit_price)
    if price < 0:
        raise PricingError("unit price cannot be negative")
    return price


def line_total(unit_price, qty: int) -> Decimal:
    """Price of `qty` units at `unit_price`, after the volume discount, rounded to cents."""
    price = _validate(unit_price, qty)
    gross = price * qty
    discount = gross * volume_discount_rate(qty)
    return _round_cents(gross - discount)


def effective_unit_price(unit_price, qty: int) -> Decimal:
    """What one unit actually costs once the volume discount is applied."""
    return _round_cents(line_total(unit_price, qty) / qty)
