# Partitioning for planning

The model format, the hypotheses and the choice of t are in
`../../coverage-proof/references/models.md`. This file covers how to *plan* with them.

## From spec to classes in five passes

1. **Inputs.** Every parameter, field, and piece of state the behavior reads: time, the
   current tier, the balance.
2. **Valid classes.** The spec's own distinctions ("Bronze/Silver/Gold/Platinum", "at least
   500 points").
3. **Boundaries.** For every comparison in the spec: on the boundary, just below, and just
   above. Put them in the model as classes. They are where off-by-one mutants live.
4. **Invalid classes.** Every rejection the spec implies, including negative, zero, empty,
   too large, wrong multiple, expired, and duplicate.
5. **Constraints.** Combinations that cannot occur, listed in `invalid`.

Then run `tmx covering <model> --strength 2 --generate`. The array is the maximum number of
table rows this behavior needs. Rows beyond it must name a branch in the code that the
model missed, and the model must be updated to include it.

## What not to enumerate

- Values inside one class ("5 points, 7 points, 9 points" when the rule is `< 500`).
- Cross-products of independent parameters. Use t-way, not the full product.
- Framework behavior, such as dataclass equality or JSON serialization of plain types,
  unless the spec customizes it.
- The same class at two levels, unit and integration.

## Worked example (loyalty tiers)

- **Behavior B1:** the tier follows lifetime points, with thresholds 0/1000/5000/20000,
  inclusive.
- **Classes:** 0, 999, 1000, 4999, 5000, 19999, 20000, and "far above" (1,000,000). That is
  8 boundary classes, giving one table of 8 rows.
- **Plus one property:** the tier is monotone non-decreasing in lifetime points.

The naive alternative is 20–40 hand-written examples, some at the same values twice and
none at 19999.
