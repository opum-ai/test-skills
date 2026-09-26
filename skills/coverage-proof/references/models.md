# Input models: what "complete" is relative to

## Partition model (category-partition, ISO/IEC/IEEE 29119-4 equivalence partitioning + BVA)

```json
{
  "unit": "loyalty.redeem",
  "hypothesis": "uniformity: every value inside a class drives the same path and outcome (classes derived from SPEC.md §3 and the branches in redeem())",
  "parameters": {
    "points":   ["below_min(<500)", "min(500)", "multiple_of_100", "not_multiple_of_100"],
    "vs_balance": ["under", "equal", "over"],
    "vs_order_total": ["under", "equal", "over"]
  },
  "invalid": [{"points": "below_min(<500)", "vs_balance": "over"}],
  "tests": {
    "tests/test_redeem.py::test_redeem[min-under-under]": {"points": "min(500)", "vs_balance": "under", "vs_order_total": "under"}
  }
}
```

- **Classes come from two places:** the spec (what should differ) and the code's branches
  (what does differ). A mismatch between them is a finding in its own right.
- **Boundaries are classes too.** `min(500)` is a class of one value, and "just below"
  and "just above" each get their own class when the code compares on them.
- **Invalid classes** (rejections, errors) need coverage like valid ones. They are where
  agent suites are weakest.
- **Choosing t:**
  - 1-way (each class once) for independent parameters;
  - 2-way by default;
  - 3-way where the spec has interacting rules, such as stacking, caps, or order of
    application.
  NIST observed no fault needing more than 6-way.

`tmx covering model.json --strength 2` lists the missing combinations and the minimal
subset. `--generate` emits a small covering array to use as table rows.

## Decision tables

When the logic is "conditions → action", each rule (column) is one row of a parametrized
test. Collapse don't-care conditions. The coverage measure (29119-4) is every rule
exercised once.

## State-transition models

For objects with a lifecycle (cart, order, lease), the states and events form the model.
- **0-switch coverage:** every valid transition once.
- **Invalid transitions:** every invalid (state, event) pair rejected.
- **1-switch coverage:** pairs of transitions, when history matters.
For anything concurrent, route to proof-skills. Interleavings are not a partition problem.

## The hypotheses, stated plainly

- **Uniformity** (Gaudel). One representative per class is as good as all of its members.
  It is violated when the code branches inside a class, so check the branches.
- **Regularity.** Behavior for small sizes generalizes to larger ones. This is the
  small-scope hypothesis (Jackson), and it justifies bounded-exhaustive tests of
  collections up to size k.
- **t-way interaction** (Kuhn et al.). Faults involve at most t parameters.

Every claim names which of these it relies on. The report repeats it.
