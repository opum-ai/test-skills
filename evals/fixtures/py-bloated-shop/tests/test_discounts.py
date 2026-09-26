from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest

from shop import discounts
from shop.discounts import FIXED, PERCENT, Coupon, CouponError, apply_coupons, is_applicable, is_expired


def test_percent_coupon_ten_on_hundred(today):
    assert apply_coupons("100.00", [Coupon("SAVE", PERCENT, 10)], today) == Decimal("10.00")


def test_percent_coupon_twenty_on_hundred(today):
    assert apply_coupons("100.00", [Coupon("SAVE", PERCENT, 20)], today) == Decimal("20.00")


def test_percent_coupon_fifteen_on_two_hundred(today):
    assert apply_coupons("200.00", [Coupon("SAVE", PERCENT, 15)], today) == Decimal("30.00")


def test_percent_coupon_five_on_forty(today):
    assert apply_coupons("40.00", [Coupon("SAVE", PERCENT, 5)], today) == Decimal("2.00")


def test_percent_coupon_twenty_five_on_eighty(today):
    assert apply_coupons("80.00", [Coupon("SAVE", PERCENT, 25)], today) == Decimal("20.00")


def test_percent_coupon_fifty_on_ten(today):
    assert apply_coupons("10.00", [Coupon("SAVE", PERCENT, 50)], today) == Decimal("5.00")


def test_fixed_coupon_five_off(today):
    assert apply_coupons("50.00", [Coupon("FIVE", FIXED, 5)], today) == Decimal("5")


def test_fixed_coupon_ten_off(today):
    assert apply_coupons("50.00", [Coupon("FIVE", FIXED, 10)], today) == Decimal("10")


def test_fixed_coupon_twenty_off(today):
    assert apply_coupons("80.00", [Coupon("FIVE", FIXED, 20)], today) == Decimal("20")


def test_fixed_coupon_three_off(today):
    assert apply_coupons("9.99", [Coupon("FIVE", FIXED, 3)], today) == Decimal("3")


def test_fixed_coupon_fractional(today):
    assert apply_coupons("15.00", [Coupon("FIVE", FIXED, "2.50")], today) == Decimal("2.50")


def test_no_coupons_no_discount(today):
    assert apply_coupons("15.00", [], today) == Decimal("0")


def test_apply_coupons_returns_decimal(today):
    assert isinstance(apply_coupons("15.00", [Coupon("X", PERCENT, 10)], today), Decimal)


def test_apply_coupons_is_deterministic(today):
    result = apply_coupons("15.00", [Coupon("X", PERCENT, 10)], today)
    assert result == result


def test_not_expired_last_year_coupon_next_year():
    coupon = Coupon("X", PERCENT, 10, expires_on=date(2025, 1, 1))
    assert is_expired(coupon, date(2024, 1, 1)) is False


def test_expired_long_ago():
    coupon = Coupon("X", PERCENT, 10, expires_on=date(2020, 1, 1))
    assert is_expired(coupon, date(2024, 1, 1)) is True


def test_no_expiry_never_expires():
    coupon = Coupon("X", PERCENT, 10)
    assert is_expired(coupon, date(2099, 1, 1)) is False


def test_is_applicable_big_order(today):
    assert is_applicable(Coupon("X", PERCENT, 10, min_spend=50), "500.00", today) is True


def test_is_applicable_tiny_order(today):
    assert is_applicable(Coupon("X", PERCENT, 10, min_spend=50), "5.00", today) is False


def test_apply_coupons_rounds_via_helper(today):
    with mock.patch("shop.discounts._round_cents", wraps=discounts._round_cents) as rounder:
        apply_coupons("100.00", [Coupon("SAVE", PERCENT, 10)], today)
    rounder.assert_called_once()


def test_apply_coupons_checks_combination_first(today):
    with mock.patch("shop.discounts.check_combination") as check, \
            mock.patch("shop.discounts.is_applicable", return_value=True) as applicable, \
            mock.patch("shop.discounts._round_cents", side_effect=lambda d: d):
        apply_coupons("100.00", [Coupon("A", PERCENT, 10), Coupon("B", FIXED, 5)], today)
    check.assert_called_once()
    assert applicable.call_count == 2


def test_coupon_smoke(today):
    coupon = Coupon("SMOKE", FIXED, 1)
    apply_coupons("10.00", [coupon], today)
    is_expired(coupon, today)


def test_coupon_is_valid_through_its_expiry_date():
    coupon = Coupon("LASTDAY", PERCENT, 10, expires_on=date(2024, 6, 30))
    assert is_expired(coupon, date(2024, 6, 30)) is False
    assert is_expired(coupon, date(2024, 7, 1)) is True
    assert apply_coupons("100.00", [coupon], date(2024, 6, 30)) == Decimal("10.00")
    assert apply_coupons("100.00", [coupon], date(2024, 7, 1)) == Decimal("0")


def test_min_spend_is_inclusive(today):
    coupon = Coupon("MIN50", FIXED, 5, min_spend="50.00")
    assert apply_coupons("50.00", [coupon], today) == Decimal("5")
    assert apply_coupons("49.99", [coupon], today) == Decimal("0")


def test_min_spend_is_judged_on_original_subtotal(today):
    half = Coupon("HALF", PERCENT, 50)
    ten_over_80 = Coupon("TENOVER80", FIXED, 10, min_spend=80)
    assert apply_coupons("100.00", [half, ten_over_80], today) == Decimal("60.00")


def test_non_stackable_coupon_cannot_be_combined(today):
    solo = Coupon("SOLO", PERCENT, 20, stackable=False)
    assert apply_coupons("100.00", [solo], today) == Decimal("20.00")
    with pytest.raises(CouponError):
        apply_coupons("100.00", [solo, Coupon("EXTRA", FIXED, 5)], today)


def test_percentages_apply_before_fixed_amounts_regardless_of_order(today):
    coupons = [Coupon("FIVE", FIXED, 5), Coupon("TEN", PERCENT, 10)]
    assert apply_coupons("100.00", coupons, today) == Decimal("15.00")


def test_percentages_compound_on_the_remaining_amount(today):
    coupons = [Coupon("A", PERCENT, 10), Coupon("B", PERCENT, 10)]
    assert apply_coupons("100.00", coupons, today) == Decimal("19.00")


def test_discount_never_exceeds_subtotal(today):
    assert apply_coupons("30.00", [Coupon("BIG", FIXED, 50)], today) == Decimal("30.00")
    assert apply_coupons("30.00", [Coupon("ALL", PERCENT, 100)], today) == Decimal("30.00")


def test_coupon_limits(today):
    three = [Coupon(c, FIXED, 1) for c in ("A", "B", "C")]
    assert apply_coupons("10.00", three, today) == Decimal("3")
    with pytest.raises(CouponError):
        apply_coupons("10.00", three + [Coupon("D", FIXED, 1)], today)
    with pytest.raises(CouponError):
        apply_coupons("10.00", [Coupon("dup", FIXED, 1), Coupon("DUP", FIXED, 1)], today)


def test_invalid_coupon_definitions_rejected():
    with pytest.raises(CouponError):
        Coupon("ZERO", FIXED, 0)
    with pytest.raises(CouponError):
        Coupon("TOOMUCH", PERCENT, "100.01")
    with pytest.raises(CouponError):
        Coupon("BOGO", "bogo", 1)
    with pytest.raises(CouponError):
        Coupon("NEG", FIXED, 1, min_spend=-1)
    assert Coupon("FREEMIN", FIXED, 1, min_spend=0).min_spend == Decimal("0")
