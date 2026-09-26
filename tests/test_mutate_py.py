"""AST mutants must be valid, distinct from the original, and cover every operator family."""
import ast

from tmx import mutate_py

SRC = '''
"""Module docstring."""
LIMIT = 10
RATE = Decimal("0.0825")


def total(xs, mode):
    if not xs:
        raise ValueError("empty")
    return round_to(sum(xs) // 2, ROUND_HALF_UP)

def f(x, flag):
    """Docstring is never mutated."""
    if x < LIMIT and not flag:
        x += 1
        log(x)
        return x * 2
    while x > 0:
        x -= 1
    return x == 0
'''


def test_every_family_yields_parseable_distinct_mutants():
    original = ast.unparse(ast.parse(SRC))
    muts = list(mutate_py.mutants_for(SRC, mutate_py.ALL_OPERATORS))
    assert all(src != original and ast.parse(src) for *_, src in muts)
    assert all("Docstring is never mutated." in src for *_, src in muts)
    assert {fam for _, fam, _, _ in muts} == set(mutate_py.ALL_OPERATORS)
    assert len({src for *_, src in muts}) == len(muts)
    descs = {desc for _, _, desc, _ in muts}
    assert {"'0.0825' -> '0.0826'", "sum() -> max()", "ROUND_HALF_UP -> ROUND_HALF_EVEN", "// -> /",
            "delete raise (validation skipped)", "10 -> 9"} <= descs    # money-shaped faults are generated
