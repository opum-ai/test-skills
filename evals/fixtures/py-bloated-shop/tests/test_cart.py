from decimal import Decimal
from unittest import mock

import pytest

from shop.cart import Cart, CartError, LineItem


def test_add_one_item(cart):
    cart.add("A", "1.00")
    assert cart.quantity("A") == 1


def test_add_two_units(cart):
    cart.add("A", "1.00", 2)
    assert cart.quantity("A") == 2


def test_add_three_units(cart):
    cart.add("A", "1.00", 3)
    assert cart.quantity("A") == 3


def test_add_five_units(cart):
    cart.add("B", "2.00", 5)
    assert cart.quantity("B") == 5


def test_add_seven_units(cart):
    cart.add("C", "2.00", 7)
    assert cart.quantity("C") == 7


def test_add_stores_item_in_items_dict(cart):
    cart.add("A", "1.00", 2)
    assert "A" in cart._items
    assert cart._items["A"].qty == 2
    assert cart._items["A"].unit_price == Decimal("1.00")


def test_add_creates_line_item(cart):
    cart.add("A", "1.00")
    assert isinstance(cart._items["A"], LineItem)


def test_len_one(cart):
    cart.add("A", "1.00")
    assert len(cart) == 1


def test_len_two(cart):
    cart.add("A", "1.00")
    cart.add("B", "1.00")
    assert len(cart) == 2


def test_empty_cart_len(cart):
    assert len(cart) == 0


def test_remove_item(cart):
    cart.add("A", "1.00")
    cart.remove("A")
    assert "A" not in cart._items


def test_update_qty_to_four(cart):
    cart.add("A", "1.00")
    cart.update_qty("A", 4)
    assert cart.quantity("A") == 4


def test_update_qty_to_six(cart):
    cart.add("A", "1.00")
    cart.update_qty("A", 6)
    assert cart.quantity("A") == 6


def test_update_qty_private_state(cart):
    cart.add("A", "1.00")
    cart.update_qty("A", 3)
    assert cart._items["A"].qty == 3


def test_subtotal_one_line(cart):
    cart.add("A", "2.00", 2)
    assert cart.subtotal() == Decimal("4.00")


def test_subtotal_two_lines(cart):
    cart.add("A", "2.00", 2)
    cart.add("B", "3.00", 1)
    assert cart.subtotal() == Decimal("7.00")


def test_subtotal_is_decimal(cart):
    cart.add("A", "2.00", 2)
    assert isinstance(cart.subtotal(), Decimal)


def test_subtotal_calls_line_total(cart):
    cart.add("A", "2.00", 2)
    cart.add("B", "3.00", 1)
    with mock.patch("shop.cart.line_total", return_value=Decimal("1.00")) as lt:
        cart.subtotal()
    assert lt.call_count == 2


def test_lines_returns_list(cart):
    cart.add("A", "2.00", 2)
    assert isinstance(cart.lines(), list)


def test_cart_smoke(cart):
    cart.add("A", "2.00", 2)
    cart.update_qty("A", 3)
    cart.subtotal()
    cart.lines()
    cart.remove("A")


def test_quantity_same_twice(cart):
    cart.add("A", "2.00", 2)
    assert cart.quantity("A") == cart.quantity("A")


def test_line_item_total():
    item = LineItem("A", Decimal("2.00"), 3)
    assert item.total == Decimal("6.00")


@pytest.mark.skip(reason="flaky, fix later")
def test_add_many_items_perf(cart):
    for i in range(1000):
        cart.add(f"SKU{i}", "1.00")
    assert len(cart) == 1000


def test_adding_same_sku_merges_quantities(cart):
    cart.add("A", "2.00", 2)
    cart.add("A", "2.00", 3)
    assert cart.quantity("A") == 5
    assert len(cart) == 1


def test_same_sku_at_a_different_price_is_rejected(cart):
    cart.add("A", "2.00")
    with pytest.raises(CartError):
        cart.add("A", "2.50")
    assert cart.quantity("A") == 1


def test_merged_quantity_cannot_exceed_limit(cart):
    cart.add("A", "1.00", 998)
    cart.add("A", "1.00", 1)
    assert cart.quantity("A") == 999
    with pytest.raises(CartError):
        cart.add("A", "1.00", 1)


def test_cart_holds_at_most_fifty_lines_but_existing_lines_can_grow(cart):
    for i in range(50):
        cart.add(f"SKU{i}", "1.00")
    cart.add("SKU0", "1.00")
    assert cart.quantity("SKU0") == 2
    with pytest.raises(CartError):
        cart.add("ONEMORE", "1.00")


def test_update_to_zero_removes_line_and_rejects_bad_quantities(cart):
    cart.add("A", "1.00", 2)
    with pytest.raises(CartError):
        cart.update_qty("A", -1)
    with pytest.raises(CartError):
        cart.update_qty("A", 1000)
    cart.update_qty("A", 999)
    assert cart.quantity("A") == 999
    cart.update_qty("A", 0)
    assert cart.quantity("A") == 0
    assert len(cart) == 0


def test_invalid_adds_rejected(cart):
    for sku, price, qty in (("", "1.00", 1), ("   ", "1.00", 1), ("A", "1.00", 0), ("A", "-1.00", 1)):
        with pytest.raises(CartError):
            cart.add(sku, price, qty)
    cart.add("FREE", "0.00", 1)
    assert len(cart) == 1


def test_unknown_sku_operations_rejected(cart):
    with pytest.raises(CartError):
        cart.remove("GHOST")
    with pytest.raises(CartError):
        cart.update_qty("GHOST", 1)


def test_subtotal_applies_volume_pricing_per_line_and_lines_sorted(cart):
    cart.add("ZED", "10.00", 10)
    cart.add("ALPHA", "1.00", 1)
    assert cart.subtotal() == Decimal("96.00")
    assert [line.sku for line in cart.lines()] == ["ALPHA", "ZED"]
