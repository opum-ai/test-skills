"""Reporting-surface and certificate tests for cover.py (TS-11).

The property tests above pin the solver's *answer*. These pin the parts of its
observable surface they leave free: the default cost, the reduction statistics,
the certificate checkers' failure messages, the removal reasons and the trade-off
curve. All assertions come from the module's documented contract, not from
running the code.
"""
from tmx import cover


def build(sets, costs=None):
    tests = {f"t{i}": {f"o{j}" for j in s} for i, s in enumerate(sets)}
    obligations = sorted({o for s in tests.values() for o in s})
    cost = dict(costs) if costs is not None else {t: 1.0 for t in tests}
    return cover.Instance(obligations, tests, cost), tests


def test_a_test_absent_from_the_cost_map_costs_one():
    inst, _ = build([{0}, {1}], costs={})
    assert inst.cost == {"t0": 1.0, "t1": 1.0}
    # o0 and o1 are each killed by only one test, so both are kept: cost 1.0 + 1.0.
    assert cover.solve(inst)["cost"] == 2.0


def test_certificate_lists_every_obligation_with_no_witness():
    inst, _ = build([{0, 1}, {2}])
    witness, missing = cover.certificate(inst, [])
    assert witness == {} and missing == ["o0", "o1", "o2"]


def test_checker_reports_a_witness_not_retained_and_one_that_does_not_discharge():
    inst, tests = build([{0}, {1}])
    killers = {o: {t for t, s in tests.items() if o in s} for o in inst.obligations}
    # o0 is killed only by t0; o1 only by t1.
    assert cover.check_certificate(killers, set(), {"o0": "t0", "o1": "t1"}) == [
        "o0: witness t0 is not retained", "o1: witness t1 is not retained"]
    # A retained witness that does not kill the obligation it is named for.
    assert cover.check_certificate(killers, {"t0", "t1"}, {"o0": "t1", "o1": "t0"}) == [
        "o0: witness t1 does not discharge it", "o1: witness t0 does not discharge it"]


def test_curve_numbers_tests_from_one():
    inst, _ = build([{0}, {1}, {2}])
    curve = cover.curve(inst)
    assert [c[0] for c in curve] == list(range(1, len(curve) + 1))


def test_reductions_record_an_essential_test_and_its_residual():
    # o1 is dischargeable only by t1, so t1 is essential; once kept, o0 is covered.
    inst, _ = build([{0}, {0, 1}])
    res = cover.solve(inst)
    assert res["keep"] == ["t1"] and res["stats"]["essential_or_forced"] == 1
    assert res["stats"]["residual_tests"] == 0 and res["stats"]["residual_obligations"] == 0


def test_forced_tests_are_kept_and_an_unknown_name_is_ignored():
    inst, _ = build([{0}, {0, 1}, {1}])
    res = cover.solve(inst, forced=["t0", "nope"])
    assert "t0" in res["keep"] and res["optimal"]


def test_odd_cycle_has_no_essential_test_and_no_forced_choice():
    n = 5
    tests = {f"t{i}": {f"o{i}", f"o{(i + 1) % n}"} for i in range(n)}
    inst = cover.Instance(sorted({o for s in tests.values() for o in s}), tests, {t: 1.0 for t in tests})
    res = cover.solve(inst)
    assert res["stats"]["essential_or_forced"] == 0
    assert res["stats"]["residual_tests"] == n and res["stats"]["residual_obligations"] == n
    assert res["optimal"] and res["cost"] == 3.0


def test_classify_removed_names_a_retained_representative():
    inst, _ = build([{0, 1}, {0, 1}, set()])
    res = cover.solve(inst)
    reasons = cover.classify_removed(inst, res["keep"])
    assert res["keep"] == ["t0"]
    assert reasons == {"t1": {"reason": "duplicate", "of": "t0"},
                       "t2": {"reason": "zero-signal"}}
