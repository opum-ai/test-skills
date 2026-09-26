# Property patterns (choose before writing examples)

| Pattern | Shape | Typical use |
|---|---|---|
| Invariant | `0 <= discount(x) <= total(x)` | caps, bounds, non-negativity, conservation |
| Round-trip | `parse(format(x)) == x` | serializers, codecs, money formatting |
| Idempotence | `f(f(x)) == f(x)` | normalization, dedup, `release_all` |
| Monotonicity | `x <= y ⇒ f(x) <= f(y)` | pricing tiers, loyalty tiers, rate limits |
| Model / reference | `impl(x) == simple_model(x)` | anything with a clear spec formula |
| Metamorphic | `f(scale(x)) == scale(f(x))`; order-insensitivity | when no exact oracle exists |
| Conservation | `sum(before) == sum(after) + consumed` | ledgers, inventory, points |
| Stateful | random operation sequences checked against a model | carts, ledgers, inventory (`RuleBasedStateMachine`, fast-check `commands`) |

## Keeping properties honest

- **The oracle comes from the spec.** If writing the property requires calling the
  function under test on the expected side, it is not a property. Write a reference
  model instead.
- **Generators must reach the boundaries.** Use `st.integers(min_value=0,
  max_value=25_000)` together with `@example(19_999)` and `@example(20_000)` to pin
  boundary classes deterministically.
- **Check what a property kills.** Run the matrix. A property that kills nothing is
  vacuous, perhaps because its generator filters everything out or its assertion always
  holds.
- **Keep 2–4 anchor examples** with literal numbers from the spec, next to each property.
  They document it, and they catch shared misunderstandings between the property and the
  code.
- **Don't let generation slow the PR tier.** Keep Hypothesis's default profile of about
  100 examples for PRs, and use a larger `max_examples` profile nightly.

```python
from hypothesis import given, example, strategies as st

@given(st.integers(min_value=0, max_value=10**7))
@example(999)
@example(1000)
@example(20000)
def test_tier_is_monotone_in_lifetime_points(p):
    assert TIER_ORDER.index(tier_for(p)) <= TIER_ORDER.index(tier_for(p + 1))
```
