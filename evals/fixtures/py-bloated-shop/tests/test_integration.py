"""End-to-end checkout flows: cart -> coupons -> tax -> inventory."""
from datetime import date
from decimal import Decimal

from shop import FIXED, PERCENT, Cart, Coupon, InventoryStore, line_total, tax_for


def test_integration_checkout_single_item_ca():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 1)
    totals = cart.checkout_totals("CA", date(2024, 3, 1))
    assert totals["subtotal"] == Decimal("20.00")
    assert totals["tax"] == Decimal("1.45")


def test_integration_checkout_single_item_tx():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 1)
    totals = cart.checkout_totals("TX", date(2024, 3, 1))
    assert totals["subtotal"] == Decimal("20.00")
    assert totals["tax"] == Decimal("1.25")


def test_integration_checkout_two_items_ca():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 1)
    cart.add("MUG", "8.00", 2)
    totals = cart.checkout_totals("CA", date(2024, 3, 1))
    assert totals["subtotal"] == Decimal("36.00")
    assert totals["total"] == Decimal("38.61")


def test_integration_checkout_with_percent_coupon():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 2)
    totals = cart.checkout_totals("OR", date(2024, 3, 1), [Coupon("TEN", PERCENT, 10)])
    assert totals["discount"] == Decimal("4.00")
    assert totals["total"] == Decimal("36.00")


def test_integration_checkout_with_fixed_coupon():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 2)
    totals = cart.checkout_totals("OR", date(2024, 3, 1), [Coupon("FIVE", FIXED, 5)])
    assert totals["discount"] == Decimal("5")
    assert totals["total"] == Decimal("35.00")


def test_integration_matches_unit_functions():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 3)
    totals = cart.checkout_totals("CA", date(2024, 3, 1))
    assert totals["subtotal"] == line_total("20.00", 3)
    assert totals["tax"] == tax_for(line_total("20.00", 3), "CA")


def test_integration_bulk_order():
    cart = Cart()
    cart.add("PEN", "1.00", 100)
    totals = cart.checkout_totals("OR", date(2024, 3, 1))
    assert totals["subtotal"] == Decimal("85.00")


def test_integration_reserve_cart_then_commit():
    cart = Cart()
    cart.add("WIDGET", "5.00", 2)
    store = InventoryStore({"WIDGET": 10})
    store.reserve_all("order-1", {line.sku: line.qty for line in cart.lines()})
    store.commit("order-1")
    assert store.on_hand("WIDGET") == 8


def test_integration_reserve_cart_available():
    cart = Cart()
    cart.add("WIDGET", "5.00", 3)
    store = InventoryStore({"WIDGET": 10})
    store.reserve_all("order-1", {line.sku: line.qty for line in cart.lines()})
    assert store.available("WIDGET") == 7


def test_integration_full_flow_runs():
    cart = Cart()
    cart.add("TSHIRT", "20.00", 1)
    store = InventoryStore({"TSHIRT": 1})
    store.reserve_all("o", {"TSHIRT": 1})
    cart.checkout_totals("NY", date(2024, 3, 1))
    store.commit("o")
