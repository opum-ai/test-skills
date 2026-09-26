from datetime import date

import pytest

from shop import Cart, InventoryStore


@pytest.fixture
def today():
    return date(2024, 6, 15)


@pytest.fixture
def cart():
    return Cart()


@pytest.fixture
def store():
    return InventoryStore({"WIDGET": 10, "GADGET": 5, "GIZMO": 0})
