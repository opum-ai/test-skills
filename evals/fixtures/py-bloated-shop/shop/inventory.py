"""In-memory inventory with per-order reservations."""
from typing import Dict, Optional


class InventoryError(Exception):
    """Raised for an invalid inventory operation."""


class InsufficientStock(InventoryError):
    """Raised when a reservation asks for more than is available."""


class InventoryStore:
    def __init__(self, stock: Optional[Dict[str, int]] = None):
        self._stock: Dict[str, int] = dict(stock or {})
        self._reserved: Dict[str, Dict[str, int]] = {}  # order id -> sku -> qty

    def restock(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise InventoryError("restock quantity must be positive")
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def on_hand(self, sku: str) -> int:
        return self._stock.get(sku, 0)

    def reserved(self, sku: str) -> int:
        return sum(order.get(sku, 0) for order in self._reserved.values())

    def available(self, sku: str) -> int:
        return self.on_hand(sku) - self.reserved(sku)

    def reserve(self, order_id: str, sku: str, qty: int) -> None:
        if qty <= 0:
            raise InventoryError("reservation quantity must be positive")
        if qty > self.available(sku):
            raise InsufficientStock(f"only {self.available(sku)} of {sku} available")
        order = self._reserved.setdefault(order_id, {})
        order[sku] = order.get(sku, 0) + qty

    def reserve_all(self, order_id: str, wanted: Dict[str, int]) -> None:
        """Reserve every line or none of them."""
        short = [sku for sku, qty in wanted.items() if qty > self.available(sku)]
        if short:
            raise InsufficientStock("insufficient stock for " + ", ".join(sorted(short)))
        for sku, qty in wanted.items():
            self.reserve(order_id, sku, qty)

    def release(self, order_id: str, sku: str, qty: Optional[int] = None) -> None:
        """Give back part (or, with no qty, all) of an order's hold on a SKU."""
        order = self._reserved.get(order_id, {})
        held = order.get(sku, 0)
        if qty is None:
            qty = held
        if qty <= 0 or qty > held:
            raise InventoryError(f"order {order_id} holds {held} of {sku}; cannot release {qty}")
        if qty == held:
            del order[sku]
        else:
            order[sku] = held - qty
        if not order:
            del self._reserved[order_id]

    def commit(self, order_id: str) -> None:
        """Turn an order's reservations into shipped stock."""
        order = self._reserved.pop(order_id, None)
        if order is None:
            raise InventoryError(f"no reservation for order {order_id}")
        for sku, qty in order.items():
            self._stock[sku] -= qty
