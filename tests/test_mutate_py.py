"""AST mutants must be valid, distinct from the original, and cover every operator family."""
import ast
import subprocess

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
    (pkg / "z.py").write_text("def second(a):\n    return a - 1\n")

    def specs(sources=("pkg/m.py",), per_line=0, seed=0, history=0):
        return pycollect.build_specs(str(tmp_path), str(tmp_path), list(sources),
                                     mutate_py.OPERATORS, per_line, history, 0,
                                     log=lambda *_: None, seed=seed)

    first = specs()
    assert [s[5] for s in first] == [s[5] for s in specs()]          # same source, same set
    assert pycollect.mutant_set_digest(first) == pycollect.mutant_set_digest(specs())
    assert pycollect.mutant_set_digest(specs(sources=("pkg/m.py", "pkg/z.py"))) == \
        pycollect.mutant_set_digest(specs(sources=("pkg/z.py", "pkg/m.py")))   # input order is irrelevant
    # The digest sorts its own input, so a caller that does not sort cannot move it.
    assert pycollect.mutant_set_digest(list(reversed(first))) == pycollect.mutant_set_digest(first)
    # The seed selects the per-line sample: same slots, a different set.
    s0, s1 = specs(per_line=1, seed=0), specs(per_line=1, seed=1)
    assert len(s0) == len(s1) and pycollect.mutant_set_digest(s0) != pycollect.mutant_set_digest(s1)
    # A source edit that changes the mutant set moves the digest...
    mod.write_text(SRC.replace("x * 2", "x * 3"))
    changed = specs()
    assert [s[5] for s in changed] != [s[5] for s in first]
    assert pycollect.mutant_set_digest(changed) != pycollect.mutant_set_digest(first)
    # ...while an edit that is not a mutation site leaves the set (and its digest) alone.
    mod.write_text(SRC.replace("x * 2", "x * 3").replace(
        '"""Docstring is never mutated."""', '"""Docstring edited, still never mutated."""'))
    assert pycollect.mutant_set_digest(specs()) == pycollect.mutant_set_digest(changed)

    # History mutants carry {file: text} rather than a string; the digest must accept both,
    # and this is the path an earlier version of the digest crashed on.
    mod.write_text("def add(a, b):\n    return a - b\n")
    git = lambda *args: subprocess.run(  # noqa: E731
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", "init")
    mod.write_text("def add(a, b):\n    return a + b\n")
    git("commit", "-qam", "fix sign bug in add")
    hist = specs(history=1)
    assert any(s[2] == "history" and isinstance(s[4], dict) for s in hist)
    assert pycollect.mutant_set_digest(hist) == pycollect.mutant_set_digest(specs(history=1))
