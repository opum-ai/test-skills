# Consolidation patterns

## Choosing the form

| The cluster looks like | Consolidate into | Keep |
|---|---|---|
| The same call, varying inputs, with expected outputs written by hand | a **parametrized table** | one row per equivalence class and boundary (on, just below, just above) |
| Rows whose expected value follows a rule | a **property** plus one or two anchor examples | the anchors document the rule with real numbers |
| The same scenario tested at unit and integration level | the **lowest level** that catches it | the higher test only if it catches something the lower one cannot (Vocke's rule) |
| Weaker copies of one strong test | the **strongest test** | its assertions; delete the rest |
| Mock-heavy tests of internal helpers | **public-API tests** without the mocks | real collaborators; mocks only at I/O boundaries |

## Table: from 9 tests to 1

Before, nine functions:
```python
def test_discount_100(): assert discount(100, False) == 95.0
def test_discount_150(): assert discount(150, False) == 142.5
def test_discount_99():  assert discount(99, False) == 99.0
# ...six more
```
After:
```python
@pytest.mark.parametrize("total,member,expected", [
    (99.99, False, 99.99),   # just below the volume threshold
    (100,   False, 95.0),    # on the threshold: 5% volume discount
    (50,    True,  45.0),    # member only: 10%
    (200,   True,  170.0),   # both stack: 15%
], ids=["below-threshold", "at-threshold", "member", "stacked"])
def test_discount(total, member, expected):
    assert discount(total, member) == expected
```
The rows are the **partition**: {below, at/above threshold} × {member, non-member}, plus
the boundary. `ids=` name the class, not the number. Add a row only when the code branches
on it.

## Property: when rows follow a rule

```python
from hypothesis import given, strategies as st

@given(total=st.decimals(min_value=0, max_value=10**6, places=2), member=st.booleans())
def test_discount_never_increases_price_and_is_monotone(total, member):
    d = discount(total, member)
    assert 0 <= d <= total                       # oracle from the spec, not from the code
    assert discount(total + 1, member) >= d - 1  # paying more never costs less (spec 3.2)
```
Keep 2–4 anchor rows beside it. Properties say what must always hold; anchors pin specific
numbers the spec states.

**The oracle rule (Article IV).** Never compute `expected` by calling the function under
test, or a copy of its logic. That cancels every fault (the "state-anchored oracle" problem).
Derive it from the spec, from a simpler reference model, or from an invariant.

## JS/TS

```ts
it.each([
  [99.99, false, 99.99],
  [100, false, 95],
])('discount(%p, %p) = %p', (total, member, expected) => {
  expect(discount(total, member)).toBe(expected)
})

import fc from 'fast-check'
test('discount never increases the price', () => {
  fc.assert(fc.property(fc.integer({min: 0, max: 1e6}), fc.boolean(), (t, m) => {
    const d = discount(t, m); return d >= 0 && d <= t
  }))
})
```

## After every batch

Re-collect the matrix, then run `tmx compare old new`. Exit 3 names each mutant no longer
killed. Put back the row or assertion that killed it.
