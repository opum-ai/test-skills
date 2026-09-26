"""Demote-before-delete (ADR-0003): the probation list, its pytest hook, and pruning.

`.test-probation.json` is a list of entries:
  {"test": "<node id>", "since": "YYYY-MM-DD", "reason": "subsumed", "witness": ["<retained test>"],
   "runs": 0, "failures": 0, "last_run": null}

A conftest hook (installed by `probation install`) marks listed tests `probation` at collection
time, so no test file changes until deletion. The PR tier runs `-m "not probation"`; nightly
runs everything and records results with `probation record --junit`.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

HOOK_BEGIN = "# --- test-skills probation hook (managed) ---"
HOOK_END = "# --- end test-skills probation hook ---"
HOOK = f'''{HOOK_BEGIN}
import json as _tsk_json, os as _tsk_os
import pytest as _tsk_pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "probation: demoted by a certified reduction; runs nightly only")
    config.addinivalue_line("markers", "quarantine: flaky, listed in .test-quarantine.json; runs nightly only")


def _tsk_ids(config, name):
    path = _tsk_os.path.join(str(config.rootpath), name)
    if not _tsk_os.path.exists(path):
        return set()
    with open(path) as f:
        return {{e["test"] for e in _tsk_json.load(f)}}


def pytest_collection_modifyitems(config, items):
    probation, quarantine = _tsk_ids(config, ".test-probation.json"), _tsk_ids(config, ".test-quarantine.json")
    for item in items:
        if item.nodeid in probation:
            item.add_marker(_tsk_pytest.mark.probation)
        if item.nodeid in quarantine:
            item.add_marker(_tsk_pytest.mark.quarantine)
{HOOK_END}
'''


def _load(path: str) -> List[dict]:
    return json.load(open(path)) if os.path.exists(path) else []


def _save(path: str, entries: List[dict]) -> None:
    with open(path, "w") as f:
        json.dump(sorted(entries, key=lambda e: e["test"]), f, indent=1)
        f.write("\n")


def add(plan_path: str, path: str, today: str = None) -> dict:
    plan = json.load(open(plan_path))
    if plan.get("uncovered"):
        raise SystemExit(f"refusing: the plan leaves {len(plan['uncovered'])} obligation(s) uncovered")
    if not plan.get("certificate"):
        raise SystemExit("refusing: the plan certifies no obligations (empty matrix?), so it proves nothing")
    today = today or dt.date.today().isoformat()
    entries = {e["test"]: e for e in _load(path)}
    added = 0
    for t, why in plan["remove"].items():
        if t in entries:
            continue
        w = why.get("by") or why.get("of") or []
        entries[t] = {"test": t, "since": today, "reason": why["reason"],
                      "witness": w if isinstance(w, list) else [w], "runs": 0, "failures": 0, "last_run": None}
        added += 1
    _save(path, list(entries.values()))
    return {"added": added, "total": len(entries)}


def install_hook(conftest: str) -> str:
    cur = open(conftest).read() if os.path.exists(conftest) else ""
    if HOOK_BEGIN in cur:
        return "present"
    with open(conftest, "a") as f:
        f.write(("\n\n" if cur.strip() else "") + HOOK)
    return "installed"


def _junit_results(paths: List[str]) -> Dict[str, str]:
    """Map pytest-style node ids to pass/fail using JUnit file+name attributes."""
    out: Dict[str, str] = {}
    for p in paths:
        for tc in ET.parse(p).getroot().iter("testcase"):
            cls, name = tc.get("classname", ""), tc.get("name", "")
            status = "fail" if (tc.find("failure") is not None or tc.find("error") is not None) else \
                "skip" if tc.find("skipped") is not None else "pass"
            parts = cls.split(".")
            # pytest: classname "tests.test_x" or "tests.test_x.TestCls"
            rank = {"fail": 2, "pass": 1, "skip": 0}
            for k in range(len(parts), 0, -1):
                mod = "/".join(parts[:k]) + ".py"
                rest = parts[k:]
                key = "::".join([mod, *rest, name])
                if rank[status] >= rank.get(out.get(key), -1):   # a failure in ANY report wins
                    out[key] = status
    return out


def record(path: str, junit: List[str], today: str = None) -> dict:
    entries = _load(path)
    res = _junit_results(junit)
    today = today or dt.date.today().isoformat()
    failed = []
    for e in entries:
        st = res.get(e["test"])
        if st in ("pass", "fail"):
            e["runs"] += 1
            e["last_run"] = today
            if st == "fail":
                e["failures"] += 1
                failed.append(e["test"])
    _save(path, entries)
    return {"recorded": sum(1 for e in entries if e["last_run"] == today), "failed": failed}


def due(entries: List[dict], days: int, min_runs: int, today: str = None) -> List[dict]:
    t = dt.date.fromisoformat(today) if today else dt.date.today()
    return [e for e in entries if e["failures"] == 0 and e["runs"] >= min_runs
            and (t - dt.date.fromisoformat(e["since"])).days >= days]


def collected_ids(root: str, python: str) -> Optional[set]:
    """Every test id pytest collects (ground truth for parametrized and fixture-param cases)."""
    import subprocess
    r = subprocess.run([python, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider"],
                       cwd=root, capture_output=True, text=True)
    ids = {ln.strip() for ln in r.stdout.splitlines() if "::" in ln and not ln.startswith(" ")}
    return ids or None


def prune(root: str, path: str, days: int, min_runs: int, dry: bool = False, today: str = None,
          collected: Optional[set] = None) -> dict:
    """Delete due tests from their files, whole functions only, atomically.

    A function goes only when EVERY case pytest collects for it is due (stacked parametrize and
    fixture params included); otherwise it is reported under partial_tables for a manual edit.
    Without `collected`, only unparametrized ids are pruned. Lines are split on \n only, to
    match AST line numbers, and every edited file must re-parse before anything is written."""
    entries = _load(path)
    ready = due(entries, days, min_runs, today)
    due_ids = {e["test"] for e in ready}
    by_func: Dict[tuple, List[str]] = {}
    for e in ready:
        f, _, rest = e["test"].split("[", 1)[0].partition("::")
        by_func.setdefault((f, rest), []).append(e["test"])
    removed, partial = [], []
    edits: Dict[str, List[tuple]] = {}
    for (f, qual), ids in sorted(by_func.items()):
        fp = os.path.join(root, f)
        if not os.path.exists(fp):
            continue
        base = f"{f}::{qual}"
        cases = {c for c in collected if c.split("[", 1)[0] == base} if collected is not None else None
        if cases is None and any("[" in i for i in ids):
            partial.append(base)          # cannot know the full case list: never guess
            continue
        if cases is not None and (not cases or not cases <= due_ids):
            partial.append(base)          # some collected case is still retained (or unknown)
            continue
        tree = ast.parse(open(fp).read())
        names = qual.split("::")
        node = _find(tree, names)
        if node is None:
            continue
        start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        edits.setdefault(f, []).append((start, node.end_lineno, names))
        removed += sorted(cases) if cases is not None else ids
    staged: Dict[str, str] = {}
    for f, spans in edits.items():
        fp = os.path.join(root, f)
        text = open(fp).read()
        tree = ast.parse(text)
        # Never empty a class: keep the last method and report it instead.
        by_cls: Dict[str, List[tuple]] = {}
        for sp in spans:
            if len(sp[2]) > 1:
                by_cls.setdefault("::".join(sp[2][:-1]), []).append(sp)
        for cls, sps in by_cls.items():
            node = _find(tree, cls.split("::"))
            if node is not None and len(sps) >= len(node.body):
                spans.remove(sps[-1])
                partial.append(f"{f}::{cls}::{sps[-1][2][-1]} (would empty the class)")
                removed = [r for r in removed if r.split("[", 1)[0] != f"{f}::{cls}::{sps[-1][2][-1]}"]
        lines = text.split("\n")
        for s, e, _ in sorted(spans, reverse=True):
            del lines[s - 1:e]
            while 0 <= s - 2 < len(lines) and s - 1 < len(lines) and not lines[s - 2].strip() \
                    and not lines[s - 1].strip():
                del lines[s - 1]
        new = "\n".join(lines)
        ast.parse(new)  # raises before any file is written
        staged[fp] = new
    if not dry:
        for fp, new in staged.items():
            with open(fp, "w") as fh:
                fh.write(new)
        gone = set(removed)
        _save(path, [e for e in entries if e["test"] not in gone])
    return {"deleted": sorted(removed), "partial_tables": sorted(set(partial)),
            "waiting": len(entries) - len(ready)}


def _find(tree, names):
    scope = tree.body
    node = None
    for n in names:
        node = next((x for x in scope if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and x.name == n), None)
        if node is None:
            return None
        scope = getattr(node, "body", [])
    return node


def compare(before: dict, after: dict) -> dict:
    """Obligations the old matrix discharged that the new one does not. Mutants are matched by
    (file, line, op, desc), not by id, so re-collected matrices compare correctly."""
    # Unique keys (`file:line:op:desc#n`) when both matrices carry them; `0 <= x <= 10` yields two
    # identical-looking `<= -> <` mutants, and a tuple key would let one hide the other.
    both = all(mu.get("key") for mu in list(before["mutants"].values()) + list(after["mutants"].values()))
    key = (lambda mu: mu["key"]) if both else \
        (lambda mu: (mu.get("file"), mu.get("line"), mu.get("op"), mu.get("desc")))  # noqa: E731
    after_by = {key(mu): mu for mu in after["mutants"].values()}
    lost, missing = [], []
    for mid, mu in before["mutants"].items():
        if mu.get("status") != "killed":
            continue
        nu = after_by.get(key(mu))
        if nu is None:
            missing.append(f"{mu['file']}:{mu['line']} {mu.get('op')} {mu.get('desc')}")
        elif nu.get("status") != "killed":
            lost.append(f"{mu['file']}:{mu['line']} {mu.get('op')} {mu.get('desc')} -> {nu.get('status')}")
    before_killed = {key(b) for b in before["mutants"].values() if b.get("status") == "killed"}
    gained = [k for k, mu in after_by.items() if mu.get("status") == "killed" and k not in before_killed]
    return {"tests_before": len(before["tests"]), "tests_after": len(after["tests"]),
            "lost": lost, "not_in_new_matrix": missing, "newly_killed": len(gained)}
