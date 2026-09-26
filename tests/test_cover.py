"""Set-cover solver and certificate (ADR-0002). Properties over random instances, one anchor."""
import itertools

from hypothesis import assume, given, settings, strategies as st

from tmx import cover

instances = st.integers(1, 8).flatmap(lambda n_tests: st.integers(1, 12).flatmap(
    lambda n_obl: st.lists(st.sets(st.integers(0, n_obl - 1), max_size=n_obl), min_size=n_tests, max_size=n_tests)))


def build(sets):
    tests = {f"t{i}": {f"o{j}" for j in s} for i, s in enumerate(sets)}
    obligations = sorted({o for s in tests.values() for o in s})
    return cover.Instance(obligations, tests, {t: 1.0 for t in tests}), tests


@settings(max_examples=150, deadline=None)
@given(instances)
def test_solution_is_a_minimum_cover_with_a_valid_certificate(sets):
    inst, tests = build(sets)
    res = cover.solve(inst)
    witness, missing = cover.certificate(inst, res["keep"])
    killers = {o: {t for t, s in tests.items() if o in s} for o in inst.obligations}
    assert missing == [] and cover.check_certificate(killers, set(res["keep"]), witness) == []
    brute = next(k for k in range(len(tests) + 1)
                 if any(set().union(*(tests[t] for t in c)) >= set(inst.obligations)
                        for c in itertools.combinations(tests, k)))
    assert res["optimal"] and len(res["keep"]) == brute


@given(instances)
def test_checker_rejects_a_certificate_missing_any_witness(sets):
    inst, tests = build(sets)
    keep = cover.solve(inst)["keep"]
    witness, _ = cover.certificate(inst, keep)
    assume(witness)
    killers = {o: {t for t, s in tests.items() if o in s} for o in inst.obligations}
    dropped = sorted(witness)[0]
    broken = {o: w for o, w in witness.items() if o != dropped}
    assert cover.check_certificate(killers, set(keep), broken) == [f"{dropped}: no witness"]


def test_removal_reasons_on_a_known_instance():
    inst, _ = build([{0, 1, 2}, {0, 1}, {0, 1, 2}, set(), {3}])
    res = cover.solve(inst)
    reasons = cover.classify_removed(inst, res["keep"])
    assert sorted(res["keep"]) == ["t0", "t4"]
    assert {t: r["reason"] for t, r in reasons.items()} == {
        "t1": "subsumed", "t2": "duplicate", "t3": "zero-signal"}


@settings(max_examples=60, deadline=None)
@given(instances)
def test_budget_exhaustion_still_yields_a_valid_cover_and_a_sound_bound(sets):
    inst, tests = build(sets)
    res = cover.solve(inst, node_budget=1)
    _, missing = cover.certificate(inst, res["keep"])
    exact = cover.solve(inst)
    assert missing == [] and res["lower_bound"] <= len(exact["keep"]) <= len(res["keep"])


@given(instances)
def test_tradeoff_curve_is_monotone_and_reaches_every_obligation(sets):
    inst, _ = build(sets)
    curve = cover.curve(inst)
    fractions = [f for _, f, _ in curve]
    assert fractions == sorted(fractions) and (not inst.obligations or fractions[-1] == 1.0)


def odd_cycle(n):
    # Test i covers obligations i and i+1. No test is essential and none dominates another, so
    # only the exact search (or, when starved of nodes, greedy plus the bound) can answer.
    tests = {f"t{i}": {f"o{i}", f"o{(i + 1) % n}"} for i in range(n)}
    return cover.Instance(sorted({o for s in tests.values() for o in s}), tests, {t: 1.0 for t in tests})


@given(st.integers(1, 9).map(lambda k: 2 * k + 1))
def test_branch_and_bound_solves_instances_the_reductions_cannot(n):
    inst = odd_cycle(n)
    res = cover.solve(inst)
    assert res["stats"]["residual_tests"] == n and res["optimal"] and len(res["keep"]) == (n + 1) // 2


@given(st.integers(2, 9).map(lambda k: 2 * k + 1))
def test_a_starved_search_still_returns_a_valid_cover_and_a_sound_bound(n):
    inst = odd_cycle(n)
    res = cover.solve(inst, node_budget=1)
    assert cover.certificate(inst, res["keep"])[1] == []
    assert res["lower_bound"] <= (n + 1) // 2 <= len(res["keep"])


def test_solver_proves_optimality_on_a_structured_instance_within_a_tight_node_budget():
    # 40 tests over 60 obligations: 12 odd cycles glued by shared "hub" obligations. Solving this
    # to proven optimality within 3,000 nodes needs the reductions, the packing bound and the
    # fewest-killers branching rule together; weakening any of them blows the budget.
    tests, n = {}, 0
    for c in range(12):
        k = 5 if c % 2 else 3
        for i in range(k):
            tests[f"t{n}"] = {f"c{c}o{i}", f"c{c}o{(i + 1) % k}"} | ({f"hub{c // 3}"} if i == 0 else set())
            n += 1
    inst = cover.Instance(sorted({o for s in tests.values() for o in s}), tests, {t: 1.0 for t in tests})
    res = cover.solve(inst, node_budget=3000)
    assert res["optimal"] and len(res["keep"]) == 6 * 2 + 6 * 3
