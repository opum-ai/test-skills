"""Language-agnostic domain faults: apply text-patch faults to throwaway copies, run any test
command that writes JUnit XML, and merge the per-test kills into a matrix.

Mutation tools know operators, not your domain: Stryker never changes a tax rate or the order of
two rules. Every agent that audited a money codebase ended up hand-writing these faults and a
runner for them; this is that runner, once.

faults.json: [{"file": "src/cart.ts", "find": "NY: 400", "replace": "NY: 450",
               "desc": "wrong NY tax rate"}, ...]   (`find` must occur exactly once)
--cmd:       the test command; {junit} is replaced by the report path, e.g.
             "npx vitest run --reporter=junit --outputFile={junit}"
             "python -m pytest -q --junitxml={junit}"
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set

from . import matrix as mx

IGNORE = shutil.ignore_patterns(".git", ".tmx", "reports", ".stryker-tmp", "__pycache__", ".pytest_cache",
                                ".hypothesis")


def junit_results(path: str) -> Dict[str, str]:
    """testcase -> 'fail' | 'pass' | 'skip', keyed by 'classname::name' with nested-describe separators
    (' > ', ' › ') normalized to spaces, which is how Stryker names the same tests."""
    out: Dict[str, str] = {}
    if not os.path.exists(path):
        return out
    for tc in ET.parse(path).getroot().iter("testcase"):
        name = re.sub(r"\s+[>›]\s+", " ", tc.get("name", ""))
        key = f"{tc.get('classname', '')}::{name}"
        bad = tc.find("failure") is not None or tc.find("error") is not None
        st = "fail" if bad else "skip" if tc.find("skipped") is not None else "pass"
        if out.get(key) != "fail":
            out[key] = st
    return out


def match_ids(junit_ids: Set[str], matrix_ids: Set[str]) -> Dict[str, str]:
    """Map JUnit ids onto matrix ids: exact, else unique same-file suffix match, else keep the JUnit id."""
    by_file: Dict[str, List[str]] = {}
    for m in matrix_ids:
        by_file.setdefault(m.split("::", 1)[0], []).append(m)
    out = {}
    for j in junit_ids:
        if j in matrix_ids:
            out[j] = j
            continue
        f, _, name = j.partition("::")
        cands = [m for fk, ms in by_file.items() if fk.endswith(f) or f.endswith(fk) for m in ms
                 if m.split("::", 1)[1] == name or m.split("::", 1)[1].endswith(name) or name.endswith(m.split("::", 1)[1])]
        out[j] = cands[0] if len(cands) == 1 else j
    return out


def _run(cmd: str, cwd: str, timeout: float) -> Optional[Dict[str, str]]:
    junit = os.path.join(cwd, ".tmx-faults-junit.xml")
    if os.path.exists(junit):
        os.remove(junit)
    try:
        subprocess.run(cmd.replace("{junit}", junit), shell=True, cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return junit_results(junit)


def run(root: str, faults: List[dict], cmd: str, matrix_path: Optional[str], out: str, jobs: int = 4,
        timeout: float = 300.0, log=print) -> dict:
    root = os.path.abspath(root)
    m = mx.load(matrix_path) if matrix_path else {"schema": mx.SCHEMA, "tests": {}, "coverage": {}, "mutants": {},
                                                  "tool": {"collector": "tmx-faults"}, "scope": {}}
    work = tempfile.mkdtemp(prefix="tmx-faults-")
    try:
        slots = []
        for j in range(jobs):
            d = os.path.join(work, f"w{j}")
            shutil.copytree(root, d, ignore=IGNORE, symlinks=True)
            slots.append(d)
        ctl = _run(cmd, slots[0], timeout)
        if not ctl or any(v == "fail" for v in ctl.values()):
            failed = sorted(k for k, v in (ctl or {}).items() if v == "fail")[:5]
            raise SystemExit(f"control run (no fault) is not green: {'no JUnit report' if not ctl else failed}. "
                             "Check --cmd writes JUnit to {junit}.")
        ids = {j: mid for j, mid in match_ids(set(ctl), set(m["tests"])).items() if ctl[j] == "pass"}
        for mid in ids.values():
            m["tests"].setdefault(mid, {"file": mid.split("::", 1)[0], "outcome": "passed"})
        free, lock = list(slots), threading.Lock()

        def one(ix_f):
            ix, f = ix_f
            rec = {"file": f["file"], "line": None, "op": "extra", "desc": f.get("desc", f["replace"])[:120],
                   "killed_by": [], "covered_by": []}
            with lock:
                d = free.pop()
            fp = os.path.join(d, f["file"])
            orig = open(fp).read() if os.path.exists(fp) else ""
            try:
                if orig.count(f["find"]) != 1:
                    rec.update(status="error", note=f"find text occurs {orig.count(f['find'])}x; fault is stale")
                    return ix, rec
                rec["line"] = orig[:orig.index(f["find"])].count("\n") + 1
                with open(fp, "w") as fh:
                    fh.write(orig.replace(f["find"], f["replace"]))
                r = _run(cmd, d, timeout)
            finally:
                if orig:
                    with open(fp, "w") as fh:
                        fh.write(orig)
                with lock:
                    free.append(d)
            if r is None:
                rec.update(status="timeout")
            else:
                failed = {k for k, v in r.items() if v == "fail"}
                # Only tests that passed in the control run can be killers. A failure of anything else
                # (a whole file that no longer compiles, a suite-level error) is not attributable.
                rec["killed_by"] = sorted({ids[k] for k in failed if k in ids})
                stray = sorted(failed - set(ids))
                if rec["killed_by"]:
                    rec["status"] = "killed"
                elif stray:
                    rec.update(status="error", note="the fault broke compilation or collection: " + ", ".join(stray)[:200])
                else:
                    rec["status"] = "survived"
            rec["key"] = f"{f['file']}:{rec['line']}:extra:{rec['desc']}"
            return ix, rec

        with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
            for ix, rec in ex.map(one, enumerate(faults)):
                m["mutants"][f"extra{ix:04d}"] = rec
        m.setdefault("tool", {})["extra_faults"] = len(faults)
        mx.save(m, out)
        killed = sum(1 for k, mu in m["mutants"].items() if k.startswith("extra") and mu["status"] == "killed")
        log(f"[tmx] {len(faults)} domain faults: {killed} killed -> {out}")
        return m
    finally:
        shutil.rmtree(work, ignore_errors=True)
