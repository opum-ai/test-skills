from decimal import Decimal
from unittest import mock

import pytest

from shop import pricing
from shop.pricing import PricingError, effective_unit_price, line_total, volume_discount_rate


def test_line_total_one_unit():
    assert line_total("5.00", 1) == Decimal("5.00")


def test_line_total_two_units():
    assert line_total("5.00", 2) == Decimal("10.00")


def test_line_total_three_units():
    assert line_total("5.00", 3) == Decimal("15.00")


def test_line_total_five_units():
    assert line_total("5.00", 5) == Decimal("25.00")


def test_line_total_six_units():
    assert line_total("2.50", 6) == Decimal("15.00")


def test_line_total_seven_units():
    assert line_total("2.50", 7) == Decimal("17.50")


def test_line_total_integer_price():
    assert line_total(4, 2) == Decimal("8.00")


def test_line_total_returns_decimal():
    assert isinstance(line_total("3.00", 2), Decimal)


def test_line_total_not_none():
    assert line_total("3.00", 2) is not None


def test_volume_rate_one():
    assert volume_discount_rate(1) == Decimal("0")


def test_volume_rate_five():
    assert volume_discount_rate(5) == Decimal("0")


def test_volume_rate_twenty():
    assert volume_discount_rate(20) == Decimal("0.05")


def test_volume_rate_seventy():
    assert volume_discount_rate(70) == Decimal("0.10")


def test_volume_rate_two_hundred():
    assert volume_discount_rate(200) == Decimal("0.15")


def test_volume_rate_is_decimal():
    assert isinstance(volume_discount_rate(25), Decimal)


def test_line_total_calls_round_cents():
    with mock.patch("shop.pricing._round_cents", wraps=pricing._round_cents) as rounder:
        line_total("3.33", 3)
    assert rounder.call_count == 1


def test_line_total_calls_validate_then_rate():
    manager = mock.Mock()
    with mock.patch("shop.pricing._validate", return_value=Decimal("2.00")) as validate, \
            mock.patch("shop.pricing.volume_discount_rate", return_value=Decimal("0")) as rate, \
            mock.patch("shop.pricing._round_cents", side_effect=lambda d: d) as rounder:
        manager.attach_mock(validate, "validate")
        manager.attach_mock(rate, "rate")
        manager.attach_mock(rounder, "round")
        line_total("2.00", 4)
    assert [c[0] for c in manager.mock_calls] == ["validate", "rate", "round"]


def test_effective_unit_price_calls_line_total():
    with mock.patch("shop.pricing.line_total", return_value=Decimal("9.00")) as lt:
        effective_unit_price("3.00", 3)
    lt.assert_called_once_with("3.00", 3)


def test_line_total_rejects_zero_qty():
    with pytest.raises(PricingError):
        line_total("1.00", 0)


def test_line_total_rejects_negative_qty():
    with pytest.raises(PricingError):
        line_total("1.00", -1)


def test_pricing_module_smoke():
    line_total("1.00", 1)
    volume_discount_rate(3)
    effective_unit_price("1.00", 1)
