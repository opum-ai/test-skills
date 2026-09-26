# Bounded-exhaustive, differential and statistical evidence

## Bounded-exhaustive (small scope)

```python
import itertools

def all_carts(max_lines=3, skus=("A", "B"), qtys=(0, 1, 2, 999, 1000)):
    for n in range(max_lines + 1):
        for lines in itertools.product(itertools.product(skus, qtys), repeat=n):
            yield list(lines)

def test_cart_total_matches_reference_for_all_small_carts():
    count = 0
    for lines in all_carts():
        assert cart_total(lines) == reference_total(lines), lines   # oracle: the spec formula
        count += 1
    assert count == 1 + 10 + 100 + 1000   # the bound is part of the claim; fail if generation shrinks
```

- Include the boundary values in the domains, for example 999/1000 around the quantity
  cap.
- Assert the enumeration count, so the claim's bound cannot silently shrink.
- **Non-vacuity:** break the reference in one place and confirm the test fails.

## Differential against a reference model (Cedar pattern)

The reference model is deliberately simple: a direct transcription of the spec, slow and
obviously right. It is reviewed, or proven (proof-skills `lean-model` can prove the model
and run it as an executable oracle). One property replaces the example suite:

```python
@given(orders())
def test_pricing_agrees_with_reference(order):
    assert price(order) == reference_price(order)
```
Keep this conformance test for good. It ties the code to the model (Article VIII).

## Statistical confidence (rule of three)

After n independent generated inputs with no failure, the 95% upper bound on the failure
probability *under the generator's distribution* is about 3/n. For example, 3,000 inputs
give < 0.1%.
- It says nothing about inputs the generator rarely produces, so state the distribution.
- It cannot demonstrate ultra-high reliability. Butler & Finelli: 10⁻⁹ needs about 3×10⁹
  tests.
- **When to stop generating (Böhme, FSE 2021):** the Good-Turing estimate of discovery
  probability (singletons / n) bounds the residual risk of finding new behavior. Stop when
  it falls below the claim's threshold.
