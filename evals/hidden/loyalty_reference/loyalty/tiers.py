"""Reference implementation of SPEC.md (used only to validate the hidden acceptance tests)."""
import enum

from .ledger import Member, PointsLedger


class Tier(enum.Enum):
    BRONZE = (0, 0, 100)
    SILVER = (1, 1000, 125)
    GOLD = (2, 5000, 150)
    PLATINUM = (3, 20000, 200)

    @property
    def threshold(self):
        return self.value[1]


ORDER = [Tier.BRONZE, Tier.SILVER, Tier.GOLD, Tier.PLATINUM]


class RedemptionError(ValueError):
    pass


def tier_for_points(lifetime_points):
    if lifetime_points < 0:
        raise ValueError("negative")
    return [t for t in ORDER if t.threshold <= lifetime_points][-1]


def points_for_purchase(amount_cents, tier):
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("amount must be a positive integer")
    return (amount_cents * tier.value[2]) // 10000


class LoyaltyAccount:
    def __init__(self, member):
        self._ledger = PointsLedger(member)
        self._tier = Tier.BRONZE
        self._lifetime = 0
        self._spent = 0

    tier = property(lambda self: self._tier)
    lifetime_points = property(lambda self: self._lifetime)
    balance = property(lambda self: self._ledger.balance - self._spent)

    def purchase(self, amount_cents):
        pts = points_for_purchase(amount_cents, self._tier)
        if pts == 0:
            return 0
        before = self._lifetime
        self._ledger.earn(pts, "purchase")
        self._lifetime += pts
        crossed = [t for t in ORDER if before < t.threshold <= self._lifetime]
        if crossed and ORDER.index(crossed[-1]) > ORDER.index(self._tier):
            self._tier = crossed[-1]
        return pts

    def redeem(self, points, order_total_cents):
        if isinstance(points, bool) or not isinstance(points, int) or points % 100 or points <= 0:
            raise RedemptionError("points must be a positive multiple of 100")
        if points > self.balance:
            raise RedemptionError("insufficient balance")
        capped = min(points, (order_total_cents // 100) * 100)
        if capped < 500:
            raise RedemptionError("below minimum")
        self._spent += capped
        return capped

    def yearly_review(self, points_earned_this_year):
        if self._tier is not Tier.BRONZE and points_earned_this_year * 2 < self._tier.threshold:
            self._tier = ORDER[ORDER.index(self._tier) - 1]
        return self._tier
