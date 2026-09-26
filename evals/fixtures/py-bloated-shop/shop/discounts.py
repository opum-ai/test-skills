"""Coupons: percentage or fixed-amount discounts with minimum spend, expiry and stacking rules.

The caller always passes `today`; nothing here reads the clock.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from .money import _round_cents, to_money

PERCENT = "percent"
FIXED = "fixed"
MAX_COUPONS = 3


class CouponError(ValueError):
    """Raised for an invalid coupon or an invalid combination of coupons."""


@dataclass(frozen=True)
class Coupon:
    code: str
    kind: str
    value: Decimal
    min_spend: Decimal = Decimal("0")
    expires_on: Optional[date] = None
    stackable: bool = True

    def __post_init__(self):
        if self.kind not in (PERCENT, FIXED):
            raise CouponError(f"unknown coupon kind: {self.kind!r}")
        value = to_money(self.value)
        if value <= 0:
            raise CouponError("coupon value must be positive")
        if self.kind == PERCENT and value > 100:
            raise CouponError("a percentage coupon cannot exceed 100")
        min_spend = to_money(self.min_spend)
        if min_spend < 0:
            raise CouponError("minimum spend cannot be negative")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "min_spend", min_spend)


def is_expired(coupon: Coupon, today: date) -> bool:
    """A coupon is still valid on its expiry date and expires the day after."""
    return coupon.expires_on is not None and today > coupon.expires_on


def is_applicable(coupon: Coupon, subtotal, today: date) -> bool:
    """Unexpired, and the subtotal meets the minimum spend (inclusive)."""
    if is_expired(coupon, today):
        return False
    return to_money(subtotal) >= coupon.min_spend


def check_combination(coupons: Sequence[Coupon]) -> None:
    """Enforce the stacking rules before any coupon is applied."""
    codes = [c.code.upper() for c in coupons]
    if len(set(codes)) != len(codes):
        raise CouponError("the same coupon cannot be used twice")
    if len(coupons) > MAX_COUPONS:
        raise CouponError(f"at most {MAX_COUPONS} coupons per order")
    if len(coupons) > 1 and any(not c.stackable for c in coupons):
        raise CouponError("a non-stackable coupon cannot be combined with others")


def apply_coupons(subtotal, coupons: Sequence[Coupon], today: date) -> Decimal:
    """Total discount for `subtotal`, never more than the subtotal itself.

    Minimum spend is judged against the original subtotal. Percentage coupons apply
    first, each to the amount remaining; fixed-amount coupons apply after them.
    """
    subtotal = to_money(subtotal)
    check_combination(coupons)
    usable = [c for c in coupons if is_applicable(c, subtotal, today)]
    remaining = subtotal
    for coupon in sorted(usable, key=lambda c: c.kind != PERCENT):
        if coupon.kind == PERCENT:
            cut = _round_cents(remaining * coupon.value / 100)
        else:
            cut = coupon.value
        remaining -= min(cut, remaining)
    return subtotal - remaining
