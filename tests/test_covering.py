"""Partition models and t-way covering arrays."""
import itertools
import json

from hypothesis import given, strategies as st

from tmx import covering

models = st.dictionaries(st.sampled_from("abcde"), st.integers(1, 4), min_size=1, max_size=5).map(
    lambda d: {k: [f"{k}{i}" for i in range(n)] for k, n in d.items()})


@given(models, st.integers(1, 3))
def test_generated_array_covers_every_t_way_combination(params, t):
    rows = covering.generate(params, t, [])
    need = covering.required(params, t, [])
    got = set().union(*(covering.covered_by(r, t) for r in rows)) if rows else set()
    assert need <= got
    assert len(rows) <= len(list(itertools.product(*params.values())))


def test_check_reports_missing_pairs_and_the_redundant_test(tmp_path, capsys):
    model = {"parameters": {"x": ["lo", "hi"], "y": ["a", "b"]},
             "tests": {"t1": {"x": "lo", "y": "a"}, "t2": {"x": "lo", "y": "a"}, "t3": {"x": "hi", "y": "b"}}}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(model))

    class A:
        model, strength, generate = str(p), 2, False
    assert covering.main(A) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["missing"] == [{"x": "hi", "y": "a"}, {"x": "lo", "y": "b"}]
    assert out["redundant_under_hypothesis"] == ["t2"]


def test_tuples_no_valid_row_can_contain_are_not_required():
    # x=a forbids y=c and y=d, so the pair (x=a, z=q) is only reachable with y=b... which is also
    # forbidden with z=q. No valid row contains (x=a, z=q): it must not be required.
    params = {"x": ["a", "b"], "y": ["b", "c", "d"], "z": ["p", "q"]}
    invalid = [{"x": "a", "y": "c"}, {"x": "a", "y": "d"}, {"y": "b", "z": "q"}]
    need = covering.required(params, 2, invalid)
    assert (("x", "a"), ("z", "q")) not in need
    rows = covering.generate(params, 2, invalid)
    assert need <= set().union(*(covering.covered_by(r, 2) for r in rows))
