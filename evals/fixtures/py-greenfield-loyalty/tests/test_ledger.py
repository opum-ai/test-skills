from datetime import date

import pytest

from loyalty import LedgerError, Member, PointsLedger


@pytest.fixture
def ledger():
    return PointsLedger(Member("m-1", "Ada", date(2023, 1, 10)))


def test_new_ledger_has_zero_balance(ledger):
    assert ledger.balance == 0
    assert ledger.entries() == []


def test_earn_accumulates_and_returns_new_balance(ledger):
    assert ledger.earn(120, "order 1") == 120
    assert ledger.earn(30, "order 2") == 150
    assert ledger.entries() == [(120, "order 1"), (30, "order 2")]


@pytest.mark.parametrize("bad", [0, -5, 1.5, True, "10"])
def test_earn_rejects_non_positive_or_non_integer_points(ledger, bad):
    with pytest.raises(LedgerError):
        ledger.earn(bad)
    assert ledger.balance == 0


def test_entries_is_a_copy(ledger):
    ledger.earn(10)
    ledger.entries().append((999, "tamper"))
    assert ledger.balance == 10


def test_member_requires_an_id():
    with pytest.raises(ValueError):
        Member("  ", "Nobody", date(2024, 1, 1))


def test_one_point_is_accepted(ledger):
    assert ledger.earn(1) == 1
