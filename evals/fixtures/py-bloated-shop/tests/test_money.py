from decimal import Decimal

import pytest

from shop.money import MoneyError, round_cents, to_money


def test_to_money_string():
    assert to_money("1.50") == Decimal("1.50")


def test_to_money_int():
    assert to_money(3) == Decimal("3")


def test_to_money_decimal():
    assert to_money(Decimal("2.25")) == Decimal("2.25")


def test_round_cents_down():
    assert round_cents("1.234") == Decimal("1.23")


def test_round_cents_up():
    assert round_cents("1.237") == Decimal("1.24")


def test_round_cents_type():
    assert isinstance(round_cents("1.20"), Decimal)


def test_to_money_float_uses_its_short_repr():
    assert to_money(0.1) == Decimal("0.1")


def test_to_money_rejects_non_amounts():
    for bad in (True, "abc", "NaN", "Infinity"):
        with pytest.raises(MoneyError):
            to_money(bad)
