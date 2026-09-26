"""The test matrix: the one interchange format every collector writes and every analysis reads.

{
  "schema": "test-matrix/1",
  "root": "/abs/path", "commit": "abc123", "generated_at": "...",
  "tool": {"collector": "pytest", "mutator": "tmx-python-ast", "operators": [...]},
  "scope": {"source": ["pkg/"], "tests": ["tests/"]},
  "tests":    {"<test id>": {"file": "tests/test_x.py", "duration": 0.01, "outcome": "passed"}},
  "coverage": {"<test id>": ["pkg/x.py:10", ...]},          # optional
  "mutants":  {"<mutant id>": {"file": "pkg/x.py", "line": 10, "op": "cmp", "desc": "< -> <=",
                               "status": "killed|survived|timeout|no_coverage|error",
                               "killed_by": [...], "covered_by": [...]}}
}

Obligations are what a reduction must preserve: `mutant:<id>` for every killed mutant and,
with lines=True, `line:<file:line>` for every covered line.
"""
from __future__ import annotations

import json
from typing import Dict, Set

SCHEMA = "test-matrix/1"
KILLED = "killed"


def load(path: str) -> dict:
    with open(path) as f:
        m = json.load(f)
    if m.get("schema") != SCHEMA:
        raise SystemExit(f"{path}: expected schema {SCHEMA}, got {m.get('schema')!r}")
    m.setdefault("tests", {})
    m.setdefault("coverage", {})
    m.setdefault("mutants", {})
    return m


def save(m: dict, path: str) -> None:
    m["schema"] = SCHEMA
    with open(path, "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)
        f.write("\n")


def obligations(m: dict, lines: bool = False) -> Dict[str, Set[str]]:
    """obligation -> set of tests (in the full suite) that discharge it."""
    tests = set(m["tests"])
    out: Dict[str, Set[str]] = {}
    for mid, mu in m["mutants"].items():
        if mu.get("status") == KILLED:
            out["mutant:" + mid] = set(mu.get("killed_by", [])) & tests
    if lines:
        for t, cov in m["coverage"].items():
            if t not in tests:
                continue
            for ln in cov:
                out.setdefault("line:" + ln, set()).add(t)
    return out


def per_test(obl: Dict[str, Set[str]], tests) -> Dict[str, Set[str]]:
    sets: Dict[str, Set[str]] = {t: set() for t in tests}
    for o, ks in obl.items():
        for t in ks:
            sets.setdefault(t, set()).add(o)
    return sets


def mutation_score(m: dict, tests=None) -> dict:
    """Detected / valid mutants. no_coverage counts as undetected and timeout as detected (Stryker)."""
    tests = set(m["tests"]) if tests is None else set(tests)
    total = killed = timeout = 0
    for mu in m["mutants"].values():
        st = mu.get("status")
        if st in ("error", "equivalent", "ignored"):
            continue
        total += 1
        if st == KILLED and tests & set(mu.get("killed_by", [])):
            killed += 1
        elif st == "timeout":
            timeout += 1
            killed += 1   # detected by hanging (Stryker/PIT convention); unattributed, so not an obligation
    return {"mutants": total, "killed": killed, "timeout": timeout,
            "score": (killed / total) if total else None}
