"""Sales tax by region, rounded to cents half-up."""
from decimal import Decimal

from .money import _round_cents, to_money

REGION_RATES = {
    "CA": Decimal("0.0725"),
    "NY": Decimal("0.08875"),
    "TX": Decimal("0.0625"),
    "OR": Decimal("0"),
}
# Regions where groceries are not taxed.
GROCERY_EXEMPT = frozenset({"NY", "TX"})


class TaxError(ValueError):
    """Raised for an unknown region or an invalid taxable amount."""


def tax_rate(region: str, category: str = "general") -> Decimal:
    key = region.strip().upper()
    if key not in REGION_RATES:
        raise TaxError(f"no tax rate for region {region!r}")
    if category == "grocery" and key in GROCERY_EXEMPT:
        return Decimal("0")
    return REGION_RATES[key]


def tax_for(amount, region: str, category: str = "general") -> Decimal:
    """Tax owed on `amount` in `region`."""
    amount = to_money(amount)
    if amount < 0:
        raise TaxError("taxable amount cannot be negative")
    return _round_cents(amount * tax_rate(region, category))
