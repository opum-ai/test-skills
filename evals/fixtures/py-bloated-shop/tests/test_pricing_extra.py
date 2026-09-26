"""More pricing coverage added while wiring up volume tiers."""
from decimal import Decimal

import pytest

from shop.pricing import MAX_QTY, PricingError, effective_unit_price, line_total, volume_discount_rate


def test_line_total_twelve_units():
    assert line_total("2.00", 12) == Decimal("22.80")


def test_line_total_fifteen_units():
    assert line_total("2.00", 15) == Decimal("28.50")


def test_line_total_twenty_units():
    assert line_total("2.00", 20) == Decimal("38.00")


def test_line_total_sixty_units():
    assert line_total("2.00", 60) == Decimal("108.00")


def test_line_total_two_hundred_units():
    assert line_total("2.00", 200) == Decimal("340.00")


def test_volume_rate_eighty():
    assert volume_discount_rate(80) == Decimal("0.10")


def test_volume_rate_five_hundred():
    assert volume_discount_rate(500) == Decimal("0.15")


def test_volume_rate_result_type():
    rate = volume_discount_rate(60)
    assert rate is not None
    assert isinstance(rate, Decimal)


def test_volume_discount_starts_at_exactly_ten_units():
    assert line_total("10.00", 9) == Decimal("90.00")
    assert line_total("10.00", 10) == Decimal("95.00")


def test_volume_tier_boundaries_at_fifty_and_one_hundred():
    assert volume_discount_rate(49) == Decimal("0.05")
    assert volume_discount_rate(50) == Decimal("0.10")
    assert volume_discount_rate(99) == Decimal("0.10")
    assert volume_discount_rate(100) == Decimal("0.15")


def test_quantity_limit_is_inclusive():
    assert line_total("1.00", MAX_QTY) == Decimal("849.15")
    with pytest.raises(PricingError):
        line_total("1.00", MAX_QTY + 1)


def test_quantity_must_be_a_real_integer():
    with pytest.raises(PricingError):
        line_total("1.00", True)
    with pytest.raises(PricingError):
        line_total("1.00", 2.0)


def test_free_items_allowed_but_negative_price_rejected():
    assert line_total("0", 3) == Decimal("0.00")
    with pytest.raises(PricingError):
        line_total("-0.01", 1)


def test_effective_unit_price_reflects_volume_discount():
    assert effective_unit_price("10.00", 10) == Decimal("9.50")
    assert effective_unit_price("1.00", 3) == Decimal("1.00")
