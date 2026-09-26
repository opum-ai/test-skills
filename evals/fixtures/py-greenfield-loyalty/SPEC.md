# Feature: tiered loyalty rewards

Status: ready for implementation. Nothing in this document exists in the code yet.

## Background

Today `loyalty` can only credit points to a member (`PointsLedger.earn`) and report a balance.
Marketing wants a tiered programme: members climb tiers as they accumulate points, higher tiers
earn points faster, points can be spent against an order, and members who stop shopping slide
down a tier at the yearly review.

## Definitions

- **Balance**: points available to spend. Earning adds to it; redeeming subtracts from it.
- **Lifetime points**: every point ever earned. Redeeming does not reduce it, so it never goes down.
- **Amounts** are integers in cents (the currency's minor unit). No floats anywhere in the API.

## 1. Tiers

| Tier | Lifetime points needed | Earning multiplier |
| --- | --- | --- |
| Bronze | 0 | 1.0 |
| Silver | 1,000 | 1.25 |
| Gold | 5,000 | 1.5 |
| Platinum | 20,000 | 2.0 |

- Thresholds are inclusive: exactly 1,000 lifetime points qualifies for Silver.
- `tier_for_points(lifetime_points)` returns the highest tier whose threshold is at or below
  `lifetime_points`. A negative argument raises `ValueError`.
- New members start at Bronze.

### Promotion

A member is promoted only when an earn makes their lifetime points **cross** a threshold: the
value before the earn is below the threshold and the value after is at or above it. The member
moves to the highest tier whose threshold was crossed, if that is higher than their current tier.
One earn can cross several thresholds (Bronze straight to Gold).

Because lifetime points only grow, each threshold is crossed at most once in a member's life.

## 2. Earning on a purchase

`account.purchase(amount_cents) -> int` credits points for a purchase and returns the points
credited.

- Base rate: 1 point per whole currency unit (100 cents).
- Points credited = `floor(amount_cents * multiplier / 100)`, using the multiplier of the tier the
  member holds **before** the purchase. Compute this exactly (integer or `Decimal` arithmetic); a
  float round-trip is not acceptable.
- `amount_cents` must be a positive integer, otherwise `ValueError`.
- Promotion (section 1) is applied after the points are credited.

## 3. Redemption

`account.redeem(points, order_total_cents) -> int` spends points against an order and returns the
discount in cents.

- 100 points are worth 1 currency unit (100 cents), so each point is worth 1 cent.
- Points are redeemed in whole currency units: `points` must be a multiple of 100.
- The minimum redemption is 500 points.
- A member cannot redeem more points than their balance.
- The discount cannot exceed the order total. If the requested points are worth more than
  `order_total_cents`, the redemption is capped at the largest multiple of 100 points that does
  not exceed the order total, and only that many points are deducted.
- The minimum applies after capping.
- Any rule violation raises `RedemptionError` and leaves the balance unchanged.

## 4. Yearly review

`account.yearly_review(points_earned_this_year) -> Tier` runs once a year and returns the tier the
member holds afterwards.

- A member is demoted when `points_earned_this_year` is **less than 50%** of the threshold of
  their current tier: Silver below 500, Gold below 2,500, Platinum below 10,000.
- A demotion drops **exactly one** tier, however few points were earned.
- Bronze has a threshold of 0 and is never demoted.
- The review never promotes.

## 5. Edge cases (these must hold)

1. A member at 999 lifetime points who earns 1 point becomes Silver. A Bronze member with 0
   lifetime points whose single purchase is worth 6,000 points becomes Gold, not Silver.
2. The purchase that triggers a promotion earns at the old tier's rate. A Silver member with
   4,900 lifetime points who spends 10,000 cents earns `floor(10000 * 1.25 / 100) = 125` points,
   not 150, and becomes Gold afterwards.
3. A purchase too small to earn a whole point (for example 79 cents at Bronze, or 79 cents at
   Silver: `floor(98.75 / 100) = 0`) is accepted, returns 0, and adds nothing to the ledger.
   `PointsLedger.earn` rejects 0, so it must not be called for such purchases.
4. Redemption capping: with a balance of 3,000, `redeem(2000, order_total_cents=1250)` deducts
   1,200 points and returns a 1,200 cent discount. With the same balance,
   `redeem(1000, order_total_cents=450)` would cap to 400 points, which is below the 500 minimum,
   so it raises and deducts nothing. `redeem(550, ...)` raises because 550 is not a multiple of 100.
5. Review boundaries: a Gold member who earned exactly 2,500 points this year stays Gold; with
   2,499 points they become Silver. A Platinum member who earned 0 points becomes Gold, not
   Bronze.
6. Redeeming points never lowers lifetime points or the tier. A member demoted from Gold to Silver
   whose lifetime points are already above 5,000 is **not** re-promoted by later purchases; they
   can only climb again by crossing the 20,000 threshold, which takes them straight to Platinum.

## API sketch

```python
class Tier(enum.Enum):
    BRONZE = ...; SILVER = ...; GOLD = ...; PLATINUM = ...

def tier_for_points(lifetime_points: int) -> Tier: ...
def points_for_purchase(amount_cents: int, tier: Tier) -> int: ...

class RedemptionError(ValueError): ...

class LoyaltyAccount:
    def __init__(self, member: Member): ...
    tier: Tier                    # read-only property
    balance: int                  # read-only property
    lifetime_points: int          # read-only property
    def purchase(self, amount_cents: int) -> int: ...
    def redeem(self, points: int, order_total_cents: int) -> int: ...
    def yearly_review(self, points_earned_this_year: int) -> Tier: ...
```

`LoyaltyAccount` should build on the existing `PointsLedger` rather than replace it. Redemptions
need to be recorded in the ledger so that the balance reflects them.

## Out of scope

Point expiry, refunds and clawback of points, tier benefits other than the earning multiplier,
and any persistence.
