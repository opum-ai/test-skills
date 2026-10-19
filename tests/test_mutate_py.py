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


def test_every_family_yields_parseable_distinct_mutants(tmp_path):
    original = ast.unparse(ast.parse(SRC))
    muts = list(mutate_py.mutants_for(SRC, mutate_py.ALL_OPERATORS))
    assert all(src != original and ast.parse(src) for *_, src in muts)
    assert all("Docstring is never mutated." in src for *_, src in muts)
    assert {fam for _, fam, _, _ in muts} == set(mutate_py.ALL_OPERATORS)
    assert len({src for *_, src in muts}) == len(muts)
    descs = {desc for _, _, desc, _ in muts}
    assert {"'0.0825' -> '0.0826'", "sum() -> max()", "ROUND_HALF_UP -> ROUND_HALF_EVEN", "// -> /",
            "delete raise (validation skipped)", "10 -> 9"} <= descs    # money-shaped faults are generated

    # Determinism (TS-25): the mutant set and its digest are a function of the source and
    # the seed only. This rides the existing test rather than taking a new slot, because the
    # suite sits at its max_tests ceiling; the article that raises it is a separate change.
    from tmx import pycollect
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    mod = pkg / "m.py"
    mod.write_text(SRC)

    def specs():
        return pycollect.build_specs(str(tmp_path), str(tmp_path), ["pkg/m.py"],
                                     mutate_py.OPERATORS, 0, 0, 0, log=lambda *_: None)

    first, second = specs(), specs()
    assert [s[5] for s in first] == [s[5] for s in second]
    assert pycollect.mutant_set_digest(first) == pycollect.mutant_set_digest(second)
    mod.write_text(SRC.replace("x * 2", "x * 3"))      # one-line change moves the digest
    changed = specs()
    assert [s[5] for s in changed] != [s[5] for s in first]
    assert pycollect.mutant_set_digest(changed) != pycollect.mutant_set_digest(first)
