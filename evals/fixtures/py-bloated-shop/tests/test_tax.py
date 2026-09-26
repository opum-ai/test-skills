from decimal import Decimal
from unittest import mock

import pytest

from shop import tax
from shop.money import round_cents
from shop.tax import TaxError, tax_for, tax_rate


def test_tax_ca_100():
    assert tax_for("100.00", "CA") == Decimal("7.25")


def test_tax_ca_200():
    assert tax_for("200.00", "CA") == Decimal("14.50")


def test_tax_ny_100():
    assert tax_for("100.00", "NY") == Decimal("8.88")


def test_tax_ny_200():
    assert tax_for("200.00", "NY") == Decimal("17.75")


def test_tax_ny_80():
    assert tax_for("80.00", "NY") == Decimal("7.10")


def test_tax_tx_100():
    assert tax_for("100.00", "TX") == Decimal("6.25")


def test_tax_tx_16():
    assert tax_for("16.00", "TX") == Decimal("1.00")


def test_tax_or_100():
    assert tax_for("100.00", "OR") == Decimal("0.00")


def test_tax_rate_ca():
    assert tax_rate("CA") == Decimal("0.0725")


def test_tax_rate_ny():
    assert tax_rate("NY") == Decimal("0.08875")


def test_tax_rate_tx():
    assert tax_rate("TX") == Decimal("0.0625")


def test_tax_returns_decimal():
    assert isinstance(tax_for("10.00", "CA"), Decimal)


def test_tax_rate_not_none():
    assert tax_rate("TX") is not None


def test_tax_for_uses_round_cents_helper():
    with mock.patch("shop.tax._round_cents", wraps=tax._round_cents) as rounder, \
            mock.patch("shop.tax.tax_rate", wraps=tax.tax_rate) as rate, \
            mock.patch("shop.tax.to_money", wraps=tax.to_money) as money:
        tax_for("10.00", "CA")
    assert money.call_count == 1
    assert rate.call_count == 1
    assert rounder.call_count == 1


def test_tax_for_with_patched_rates():
    with mock.patch.dict("shop.tax.REGION_RATES", {"ZZ": Decimal("0.5")}):
        assert tax_for("10.00", "ZZ") == Decimal("5.00")


def test_tax_rounds_half_cents_up():
    assert tax_for("2.00", "CA") == Decimal("0.15")  # 0.145 -> 0.15, not banker's 0.14
    assert round_cents("0.125") == Decimal("0.13")


def test_groceries_exempt_only_where_the_law_says():
    assert tax_for("100.00", "NY", category="grocery") == Decimal("0.00")
    assert tax_for("100.00", "TX", category="grocery") == Decimal("0.00")
    assert tax_for("100.00", "CA", category="grocery") == Decimal("7.25")
    assert tax_rate("NY", category="general") == Decimal("0.08875")


def test_region_codes_are_normalised_and_unknown_regions_rejected():
    assert tax_rate(" ca ") == Decimal("0.0725")
    with pytest.raises(TaxError):
        tax_rate("ZZ")


def test_negative_taxable_amount_rejected_zero_allowed():
    assert tax_for("0", "CA") == Decimal("0.00")
    with pytest.raises(TaxError):
        tax_for("-0.01", "CA")
