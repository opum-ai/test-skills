"""Hidden acceptance tests for SPEC.md (graders only; never shown to the agent under test).
Every assertion comes from the spec text; edge cases 1-6 are covered verbatim."""
from datetime import date

import pytest

from loyalty import LoyaltyAccount, Member, RedemptionError, Tier, points_for_purchase, tier_for_points


def acct():
    return LoyaltyAccount(Member("m1", "Ann", date(2024, 1, 1)))


def earn_to(a, lifetime):
    """Drive lifetime points to exactly `lifetime` at Bronze-rate purchases where possible."""
    while a.lifetime_points < lifetime:
        need = lifetime - a.lifetime_points
        mult = {Tier.BRONZE: 100, Tier.SILVER: 125, Tier.GOLD: 150, Tier.PLATINUM: 200}[a.tier]
        cents = -(-need * 10000 // mult)
        while (cents * mult) // 10000 > need:
            cents -= 1
        if (cents * mult) // 10000 == 0:
            cents = -(-10000 // mult)
        a.purchase(cents)
    return a


@pytest.mark.parametrize("points,tier", [(0, Tier.BRONZE), (999, Tier.BRONZE), (1000, Tier.SILVER),
                                         (4999, Tier.SILVER), (5000, Tier.GOLD), (19999, Tier.GOLD),
                                         (20000, Tier.PLATINUM), (10**7, Tier.PLATINUM)])
def test_tier_thresholds_inclusive(points, tier):
    assert tier_for_points(points) is tier


def test_negative_lifetime_rejected():
    with pytest.raises(ValueError):
        tier_for_points(-1)


@pytest.mark.parametrize("cents,tier,pts", [(10000, Tier.BRONZE, 100), (10000, Tier.SILVER, 125),
                                            (10000, Tier.GOLD, 150), (10000, Tier.PLATINUM, 200),
                                            (79, Tier.BRONZE, 0), (79, Tier.SILVER, 0), (199, Tier.SILVER, 2),
                                            (133, Tier.GOLD, 1), (12345, Tier.SILVER, 154)])
def test_points_for_purchase_exact_floor(cents, tier, pts):
    assert points_for_purchase(cents, tier) == pts


@pytest.mark.parametrize("bad", [0, -100])
def test_purchase_amount_must_be_positive(bad):
    with pytest.raises(ValueError):
        acct().purchase(bad)


def test_new_member_is_bronze_with_nothing():
    a = acct()
    assert (a.tier, a.balance, a.lifetime_points) == (Tier.BRONZE, 0, 0)


def test_edge1_crossing_999_to_1000_promotes_to_silver():
    a = earn_to(acct(), 999)
    assert a.tier is Tier.BRONZE
    a.purchase(100)
    assert a.tier is Tier.SILVER and a.lifetime_points == 1000


def test_edge1_single_purchase_jumps_bronze_to_gold():
    a = acct()
    assert a.purchase(600000) == 6000
    assert a.tier is Tier.GOLD


def test_edge2_promoting_purchase_earns_at_old_rate():
    a = earn_to(acct(), 4900)
    assert a.tier is Tier.SILVER
    assert a.purchase(10000) == 125
    assert a.tier is Tier.GOLD and a.lifetime_points == 5025


def test_edge3_tiny_purchase_earns_nothing_and_does_not_touch_ledger():
    a = acct()
    assert a.purchase(79) == 0
    assert (a.balance, a.lifetime_points) == (0, 0)


def test_edge4_redemption_capped_to_order_total():
    a = earn_to(acct(), 3000)
    assert a.redeem(2000, order_total_cents=1250) == 1200
    assert a.balance == 1800 and a.lifetime_points == 3000


@pytest.mark.parametrize("points,total", [(1000, 450), (550, 10000), (400, 10000), (3100, 100000), (0, 10000)])
def test_edge4_invalid_redemptions_raise_and_change_nothing(points, total):
    a = earn_to(acct(), 3000)
    with pytest.raises(RedemptionError):
        a.redeem(points, order_total_cents=total)
    assert a.balance == 3000


def test_redeem_exactly_minimum_and_exactly_balance():
    a = earn_to(acct(), 500)
    assert a.redeem(500, order_total_cents=500) == 500
    assert a.balance == 0


@pytest.mark.parametrize("start,earned,after", [
    (5000, 2500, Tier.GOLD), (5000, 2499, Tier.SILVER), (20000, 0, Tier.GOLD), (20000, 10000, Tier.PLATINUM),
    (1000, 499, Tier.BRONZE), (1000, 500, Tier.SILVER), (0, 0, Tier.BRONZE), (5000, 10**6, Tier.GOLD)])
def test_edge5_yearly_review_boundaries(start, earned, after):
    a = earn_to(acct(), start)
    assert a.yearly_review(earned) is after
    assert a.tier is after


def test_edge6_redeeming_never_lowers_lifetime_or_tier():
    a = earn_to(acct(), 6000)
    a.redeem(5000, order_total_cents=100000)
    assert a.tier is Tier.GOLD and a.lifetime_points == 6000


def test_edge6_demoted_member_not_repromoted_until_next_threshold():
    a = earn_to(acct(), 6000)
    assert a.yearly_review(0) is Tier.SILVER
    a.purchase(100000)                      # earns at Silver rate, crosses nothing new
    assert a.tier is Tier.SILVER
    earn_to(a, 20000)
    assert a.tier is Tier.PLATINUM


def test_redemptions_are_recorded_so_balance_reflects_them():
    a = earn_to(acct(), 2000)
    a.redeem(1000, order_total_cents=5000)
    a.purchase(10000)
    assert a.balance == 1000 + 125
