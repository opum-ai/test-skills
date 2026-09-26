"""Partition models and t-way coverage: make "these N tests are enough" a checkable claim.

A model declares the input parameters of one unit, the equivalence classes (partitions) of
each, and optionally constraints, then lists the existing tests as class assignments:

{
  "unit": "pricing.discount",
  "hypothesis": "uniformity: any value in a class exercises the same path (category-partition)",
  "parameters": {
    "total":  ["zero", "below_threshold", "at_threshold", "above_threshold"],
    "member": ["yes", "no"]
  },
  "invalid": [{"total": "zero", "member": "yes"}],        # excluded combinations (optional)
  "tests": {"tests/test_p.py::test_a": {"total": "below_threshold", "member": "yes"}, ...}
}

`check` reports every t-way combination of classes no test covers and every test that adds
no combination the others lack (redundant under the stated hypothesis). `--generate` emits a
small covering array (greedy, AETG-style) as the target test set.

The claim this supports is conditional and must be stated with it: *if* the uniformity
hypothesis holds for these classes and faults involve at most t parameters (NIST's
interaction rule: most faults need 1-2, none observed beyond 6), then the covering set
detects what the exhaustive product would.
"""
from __future__ import annotations

import itertools
import json
from typing import Dict, List, Tuple

from . import cover


def _valid(assign: Dict[str, str], invalid: List[Dict[str, str]]) -> bool:
    return not any(all(assign.get(k) == v for k, v in bad.items()) for bad in invalid)


def required(params: Dict[str, List[str]], t: int, invalid, feasibility_limit: int = 200_000) -> set:
    """t-way combinations some fully valid row can contain. A tuple that no valid row extends
    (constraints forbid every completion) is infeasible and never required."""
    names = sorted(params)
    t = min(t, len(names))
    size = 1
    for n in names:
        size *= len(params[n])
    if size <= feasibility_limit:
        need = set()
        for vals in itertools.product(*(params[n] for n in names)):
            row = dict(zip(names, vals))
            if _valid(row, invalid):
                need |= covered_by(row, t)
        return need
    need = set()
    for combo in itertools.combinations(names, t):
        for vals in itertools.product(*(params[n] for n in combo)):
            a = dict(zip(combo, vals))
            if _valid(a, invalid):
                need.add(tuple(sorted(a.items())))
    return need


def covered_by(assign: Dict[str, str], t: int) -> set:
    names = sorted(assign)
    return {tuple(sorted((n, assign[n]) for n in combo)) for combo in itertools.combinations(names, min(t, len(names)))}


def generate(params: Dict[str, List[str]], t: int, invalid, seed_rows=()) -> List[Dict[str, str]]:
    names = sorted(params)
    need = required(params, t, invalid)
    rows = [dict(r) for r in seed_rows]
    for r in rows:
        need -= covered_by(r, t)
    full = [dict(zip(names, vals)) for vals in itertools.product(*(params[n] for n in names))]
    cands = [(i, r, covered_by(r, t)) for i, r in enumerate(full) if _valid(r, invalid)]
    while need:
        best = max(cands, key=lambda c: (len(c[2] & need), -c[0]))
        gain = best[2] & need
        if not gain:
            break
        rows.append(best[1])
        need -= gain
    return rows


def main(a) -> int:
    with open(a.model) as f:
        model = json.load(f)
    params = model["parameters"]
    invalid = model.get("invalid", [])
    t = a.strength
    need = required(params, t, invalid)
    tests = model.get("tests", {})
    got: Dict[Tuple, List[str]] = {}
    for tid, assign in tests.items():
        unknown = {k: v for k, v in assign.items() if k not in params or v not in params[k]}
        if unknown:
            print(f"error: {tid} uses undeclared classes {unknown}")
            return 2
        for c in covered_by(assign, t):
            got.setdefault(c, []).append(tid)
    missing = sorted(need - set(got))
    # Jointly sound redundancy: the minimum subset that still covers every covered combination.
    combos = sorted(repr(c) for c in need if c in got)
    sets = {tid: {repr(c) for c in covered_by(assign, t) if c in need} for tid, assign in tests.items()}
    inst = cover.Instance(combos, sets, {tid: 1.0 for tid in tests})
    res = cover.solve(inst)
    redundant = sorted(set(tests) - set(res["keep"]))
    product = 1
    for v in params.values():
        product *= len(v)
    out = {"unit": model.get("unit"), "strength": t, "hypothesis": model.get("hypothesis"),
           "classes": {k: len(v) for k, v in params.items()}, "exhaustive_product": product,
           "required_combinations": len(need), "covered": len(need) - len(missing),
           "missing": [dict(c) for c in missing], "tests": len(tests),
           "minimal_subset": res["keep"], "minimal_is_optimal": res["optimal"],
           "redundant_under_hypothesis": redundant}
    if a.generate:
        rows = generate(params, t, invalid)
        out["covering_array"] = rows
        out["covering_array_size"] = len(rows)
    print(json.dumps(out, indent=1))
    return 0 if not missing else 1
