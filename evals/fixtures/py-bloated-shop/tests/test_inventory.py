import time
from unittest import mock

import pytest

from shop.inventory import InsufficientStock, InventoryError, InventoryStore


def test_reserve_one_widget(store):
    store.reserve("o1", "WIDGET", 1)
    assert store.available("WIDGET") == 9


def test_reserve_two_widgets(store):
    store.reserve("o1", "WIDGET", 2)
    assert store.available("WIDGET") == 8


def test_reserve_three_widgets(store):
    store.reserve("o1", "WIDGET", 3)
    assert store.available("WIDGET") == 7


def test_reserve_four_widgets(store):
    store.reserve("o1", "WIDGET", 4)
    assert store.available("WIDGET") == 6


def test_reserve_one_gadget(store):
    store.reserve("o1", "GADGET", 1)
    assert store.available("GADGET") == 4


def test_reserve_two_gadgets(store):
    store.reserve("o1", "GADGET", 2)
    assert store.available("GADGET") == 3


def test_on_hand_widget(store):
    assert store.on_hand("WIDGET") == 10


def test_on_hand_unknown(store):
    assert store.on_hand("NOPE") == 0


def test_reserve_updates_private_dict(store):
    store.reserve("o1", "WIDGET", 2)
    assert store._reserved == {"o1": {"WIDGET": 2}}


def test_restock_updates_private_stock(store):
    store.restock("WIDGET", 5)
    assert store._stock["WIDGET"] == 15


def test_restock_new_sku(store):
    store.restock("NEW", 3)
    assert store.on_hand("NEW") == 3


def test_reserve_checks_available(store):
    with mock.patch.object(InventoryStore, "available", return_value=100) as available:
        store.reserve("o1", "WIDGET", 50)
    available.assert_called_once_with("WIDGET")


def test_available_calls_on_hand_and_reserved(store):
    with mock.patch.object(InventoryStore, "on_hand", return_value=10) as on_hand, \
            mock.patch.object(InventoryStore, "reserved", return_value=3) as reserved:
        assert store.available("WIDGET") == 7
    on_hand.assert_called_once_with("WIDGET")
    reserved.assert_called_once_with("WIDGET")


def test_reserve_all_calls_reserve_per_line(store):
    with mock.patch.object(InventoryStore, "reserve") as reserve, \
            mock.patch.object(InventoryStore, "available", return_value=99), \
            mock.patch.object(InventoryStore, "reserved", return_value=0):
        store.reserve_all("o1", {"WIDGET": 1, "GADGET": 1})
    assert reserve.call_count == 2
    assert reserve.call_args_list[0] == mock.call("o1", "WIDGET", 1)


def test_reservation_is_visible_after_a_moment(store):
    store.reserve("o1", "WIDGET", 2)
    time.sleep(0.2)  # wait for reservation
    assert store.reserved("WIDGET") == 2


def test_store_not_none():
    assert InventoryStore() is not None


def test_store_smoke(store):
    store.reserve("o1", "WIDGET", 1)
    store.release("o1", "WIDGET")
    store.restock("GADGET", 1)


def test_release_does_not_crash(store):
    store.reserve("o1", "WIDGET", 2)
    store.release("o1", "WIDGET", 1)


@pytest.mark.skip(reason="flaky, fix later")
def test_concurrent_reservations(store):
    store.reserve("o1", "WIDGET", 5)
    store.reserve("o2", "WIDGET", 5)
    assert store.available("WIDGET") == 0


def test_can_reserve_exactly_what_is_available_but_not_more(store):
    store.reserve("o1", "WIDGET", 6)
    store.reserve("o2", "WIDGET", 4)
    assert store.available("WIDGET") == 0
    with pytest.raises(InsufficientStock):
        store.reserve("o3", "WIDGET", 1)


def test_releasing_more_than_reserved_raises(store):
    store.reserve("o1", "WIDGET", 3)
    with pytest.raises(InventoryError):
        store.release("o1", "WIDGET", 4)
    assert store.reserved("WIDGET") == 3
    with pytest.raises(InventoryError):
        store.release("o1", "GADGET")
    with pytest.raises(InventoryError):
        store.release("o1", "WIDGET", 0)


def test_partial_then_full_release(store):
    store.reserve("o1", "WIDGET", 3)
    store.reserve("o1", "GADGET", 1)
    store.release("o1", "WIDGET", 1)
    assert store.reserved("WIDGET") == 2
    store.release("o1", "WIDGET")
    store.release("o1", "GADGET")
    assert store.available("WIDGET") == 10
    with pytest.raises(InventoryError):
        store.commit("o1")  # releasing everything drops the order


def test_reserve_all_is_all_or_nothing(store):
    with pytest.raises(InsufficientStock):
        store.reserve_all("o1", {"WIDGET": 2, "GADGET": 6})
    assert store.reserved("WIDGET") == 0
    store.reserve_all("o1", {"WIDGET": 2, "GADGET": 5})
    assert store.available("GADGET") == 0


def test_commit_ships_reserved_stock(store):
    store.reserve("o1", "WIDGET", 3)
    store.reserve("o1", "GADGET", 2)
    store.commit("o1")
    assert (store.on_hand("WIDGET"), store.on_hand("GADGET")) == (7, 3)
    assert store.reserved("WIDGET") == 0
    with pytest.raises(InventoryError):
        store.commit("o1")


def test_non_positive_quantities_rejected(store):
    with pytest.raises(InventoryError):
        store.reserve("o1", "WIDGET", 0)
    with pytest.raises(InventoryError):
        store.restock("WIDGET", 0)
    store.restock("WIDGET", 1)
    assert store.on_hand("WIDGET") == 11
