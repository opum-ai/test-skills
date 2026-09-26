# Test plan: <change>

**Rigor:** R3 Standard (project default R3; paths touched: loyalty/ → standard tier)
**Budget:** 14 planned cases (policy allows 8 per change without a trailer →
`Test-Budget: new tiering feature; 3 tables + 2 properties`)

## Behaviors

| ID | Behavior (observable) | Risk tier | Evidence form | Test |
|---|---|---|---|---|
| B1 | Tier follows lifetime points (0/1000/5000/20000, inclusive) | standard | table (8 boundary rows) + monotone property | `test_tier_for`, `test_tier_monotone` |
| B2 | Earned points = floor(cents × multiplier / 100) at the pre-purchase tier | critical | table (4 tiers × rounding edge) | `test_earn` |
| B3 | Redemption rejects < 500, non-multiples of 100, over balance | critical | table from covering array (t=2, 6 rows) | `test_redeem_rejects` |
| B4 | Yearly review demotes at most one tier | standard | property over generated histories | `test_review_demotes_at_most_one` |
| B5 | Bronze never demoted | standard | — (covered by B4's property; stated here) | — |

## Partition models

`testing/partitions/loyalty.redeem.json`: t=2, 6 rows, hypothesis: uniformity per SPEC §3.

## Not tested, and why

- Dataclass equality: framework behavior.
- Serialization: out of scope for this change.

## Result (filled in after Prune)

- Written 19 cases, pruned 5 (scaffolding and duplicate rows): **tests +14 / −0**.
- Mutation on changed code: 96% (48/50). Survivors: `ledger.py:41 cmp` is equivalent
  (the clamp); `tiers.py:12 const` was a real gap, and the 19999 row was added.
- Gate: PASS at R3.
