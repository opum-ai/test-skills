"""The shopping cart: lines keyed by SKU, and checkout totals."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Sequence

from .discounts import Coupon, apply_coupons
from .money import ZERO, to_money
from .pricing import MAX_QTY, line_total
from .tax import tax_for


class CartError(ValueError):
    """Raised for an invalid cart operation."""


@dataclass
class LineItem:
    sku: str
    unit_price: Decimal
    qty: int

    @property
    def total(self) -> Decimal:
        return line_total(self.unit_price, self.qty)


class Cart:
    MAX_LINES = 50

    def __init__(self):
        self._items: Dict[str, LineItem] = {}

    def __len__(self) -> int:
        return len(self._items)

    def add(self, sku: str, unit_price, qty: int = 1) -> None:
        """Add `qty` units; adding a SKU already in the cart increases its quantity."""
        if not sku or not sku.strip():
            raise CartError("a SKU is required")
        if qty <= 0:
            raise CartError("quantity must be positive")
        price = to_money(unit_price)
        if price < 0:
            raise CartError("price cannot be negative")
        existing = self._items.get(sku)
        if existing is not None:
            if existing.unit_price != price:
                raise CartError(f"{sku} is already in the cart at a different price")
            qty += existing.qty
        elif len(self._items) >= self.MAX_LINES:
            raise CartError(f"a cart holds at most {self.MAX_LINES} lines")
        if qty > MAX_QTY:
            raise CartError(f"at most {MAX_QTY} units of {sku}")
        self._items[sku] = LineItem(sku, price, qty)

    def remove(self, sku: str) -> None:
        if sku not in self._items:
            raise CartError(f"{sku} is not in the cart")
        del self._items[sku]

    def update_qty(self, sku: str, qty: int) -> None:
        """Set the quantity of a line; zero removes it."""
        if sku not in self._items:
            raise CartError(f"{sku} is not in the cart")
        if qty < 0:
            raise CartError("quantity cannot be negative")
        if qty == 0:
            del self._items[sku]
            return
        if qty > MAX_QTY:
            raise CartError(f"at most {MAX_QTY} units of {sku}")
        self._items[sku].qty = qty

    def quantity(self, sku: str) -> int:
        item = self._items.get(sku)
        return item.qty if item is not None else 0

    def lines(self) -> List[LineItem]:
        return [self._items[sku] for sku in sorted(self._items)]

    def subtotal(self) -> Decimal:
        return sum((item.total for item in self._items.values()), ZERO)

    def checkout_totals(self, region: str, today: date, coupons: Sequence[Coupon] = ()) -> dict:
        """Subtotal, coupon discount, tax on the discounted amount, and the grand total."""
        if not self._items:
            raise CartError("cannot check out an empty cart")
        subtotal = self.subtotal()
        discount = apply_coupons(subtotal, coupons, today)
        taxable = subtotal - discount
        tax = tax_for(taxable, region)
        return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": taxable + tax}
