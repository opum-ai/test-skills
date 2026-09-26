#!/usr/bin/env python3
"""Objective graders for the test-skills eval cases. Prints one JSON object of metrics.

  grade.py <case-name> <workspace> --python <interpreter with pytest+coverage+hypothesis>

The graders never trust the agent's own claims: they re-run the suite, re-collect kill
matrices with tmx, compare against a pristine copy of the fixture, and (for the greenfield
case) run hidden acceptance tests the agent never saw.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMX = os.path.join(HERE, "..", "skills", "test-audit", "scripts", "tmx.py")
PR_TIER = "not probation and not quarantine and not slow"
HIDDEN_TOTAL = 43   # tests in hidden/test_loyalty_acceptance.py (all pass on hidden/loyalty_reference)
HISTORY = ("coupon expiry", "banker", "releasing more than was reserved")


def run(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def tree_hash(root, sub):
    h = hashlib.sha256()
    base = os.path.join(root, sub)
    for d, dirs, fs in sorted(os.walk(base)):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for f in sorted(fs):
            if f.endswith(".pyc"):
                continue
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, base).encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()


def pytest_count(py, cwd, marker=None, paths=("tests",), respect_config=False):
    # By default addopts is cleared so counts are comparable; governance cases respect the project's
    # own config (its quarantine/probation deselection is part of what is being graded).
    args = [py, "-m", "pytest", "-q", *([] if respect_config else ["-o", "addopts="]), "-p", "no:cacheprovider", *paths]
    if marker:
        args += ["-m", marker]
    r = run(args, cwd)
    lines = [ln for ln in r.stdout.splitlines() if re.search(r"\d+ (passed|failed|error|skipped|deselected)", ln)]
    tail = lines[-1] if lines else (r.stdout.strip().splitlines() or [""])[-1]
    n = lambda k: int(m.group(1)) if (m := re.search(rf"(\d+) {k}", tail)) else 0  # noqa: E731
    return {"exit": r.returncode, "passed": n("passed"), "failed": n("failed"), "errors": n("error"),
            "skipped": n("skipped"), "summary": tail}


def pristine(fixture, dest):
    subprocess.run([os.path.join(HERE, "setup_ws.sh"), fixture, dest], check=True, capture_output=True)
    return dest


def matrix(py, cwd, src, out, marker=None, history=0):
    args = [py, TMX, "collect-pytest", "--src", src, "--tests", "tests", "-o", out, "--jobs", "8"]
    if marker:
        args += ["--pytest-arg=-m", f"--pytest-arg={marker}"]
    if history:
        args += ["--history", str(history)]
    r = run(args, cwd)
    if r.returncode != 0:
        return None, r.stderr[-1500:] + r.stdout[-500:]
    return json.load(open(out)), None


def killed_keys(m):
    return {(mu["file"], mu["line"], mu["op"], re.sub(r"revert [0-9a-f]{8}: ", "", mu["desc"]))
            for mu in m["mutants"].values() if mu["status"] == "killed"}


def smells(ws, py):
    r = run([sys.executable, TMX, "smells", "tests", "-o", os.path.join(ws, ".grade-smells.json")], ws)
    try:
        return json.load(open(os.path.join(ws, ".grade-smells.json")))["by_kind"]
    except Exception:
        return {"error": r.stdout[-300:]}


def grade_shop(case, ws, py, tmp):
    fix = pristine("py-bloated-shop", os.path.join(tmp, "pristine"))
    out = {"src_unchanged": tree_hash(ws, "shop") == tree_hash(fix, "shop"),
           "tests_unchanged": tree_hash(ws, "tests") == tree_hash(fix, "tests")}
    out["pr_tier"] = pytest_count(py, ws, PR_TIER)
    out["all"] = pytest_count(py, ws)
    out["smells_after"] = smells(ws, py)
    if case == "shop-audit":
        return out
    # Kill preservation: graft the agent's tests onto the pristine history, then compare.
    before, err = matrix(py, fix, "shop", os.path.join(tmp, "before.json"), history=5)
    graft = os.path.join(tmp, "graft")
    shutil.copytree(fix, graft, symlinks=True)
    shutil.rmtree(os.path.join(graft, "tests"))
    shutil.copytree(os.path.join(ws, "tests"), os.path.join(graft, "tests"))
    for f in ("conftest.py", "pyproject.toml", "pytest.ini", "setup.cfg", ".test-probation.json", ".test-quarantine.json"):
        if os.path.exists(os.path.join(ws, f)):
            shutil.copy(os.path.join(ws, f), os.path.join(graft, f))
    after, err2 = matrix(py, graft, "shop", os.path.join(tmp, "after.json"), marker=PR_TIER, history=5)
    if before is None or after is None:
        out["matrix_error"] = err or err2
        return out
    kb, ka = killed_keys(before), killed_keys(after)
    lost = sorted(kb - ka)
    out["kills_before"], out["kills_after_pr_tier"] = len(kb), len(ka)
    out["lost_kills"] = [f"{f}:{ln} {op} {d}" for f, ln, op, d in lost][:30]
    out["lost_kill_count"] = len(lost)
    hist_after = [mu for mu in after["mutants"].values() if mu["op"] == "history"]
    out["history_mutants_killed"] = sum(1 for mu in hist_after if mu["status"] == "killed")
    out["history_mutants_total"] = len(hist_after)
    return out


def grade_loyalty(ws, py, tmp):
    fix = pristine("py-greenfield-loyalty", os.path.join(tmp, "pristine"))
    out = {}
    hid = os.path.join(tmp, "hidden")
    os.makedirs(hid)
    shutil.copytree(os.path.join(ws, "loyalty"), os.path.join(hid, "loyalty"))
    shutil.copy(os.path.join(HERE, "hidden", "test_loyalty_acceptance.py"), hid)
    r = run([py, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider", "test_loyalty_acceptance.py"], hid,
            env=dict(os.environ, PYTHONPATH=hid))
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
    p = int(m.group(1)) if (m := re.search(r"(\d+) passed", tail)) else 0
    f = int(m.group(1)) if (m := re.search(r"(\d+) failed", tail)) else 0
    e = int(m.group(1)) if (m := re.search(r"(\d+) error", tail)) else 0
    out["hidden_acceptance"] = {"passed": p, "total": max(p + f + e, HIDDEN_TOTAL), "summary": tail}
    suite = pytest_count(py, ws)
    base = pytest_count(py, fix)
    out["suite"] = suite
    out["tests_added"] = suite["passed"] + suite["skipped"] - (base["passed"] + base["skipped"])
    m, err = matrix(py, ws, "loyalty", os.path.join(tmp, "m.json"))
    if m:
        new_files = [f for f in {mu["file"] for mu in m["mutants"].values()} if not f.endswith(("ledger.py", "__init__.py"))]
        sub = [mu for mu in m["mutants"].values() if mu["file"] in new_files and mu["status"] not in ("error",)]
        k = sum(1 for mu in sub if mu["status"] == "killed")
        out["mutation_new_code"] = {"files": sorted(new_files), "killed": k, "total": len(sub),
                                    "score": round(k / len(sub), 3) if sub else None}
    else:
        out["matrix_error"] = err
    out["smells"] = smells(ws, py)
    src = "".join(open(os.path.join(d, x)).read() for d, _, fs in os.walk(os.path.join(ws, "tests")) for x in fs if x.endswith(".py"))
    out["property_tests"] = len(re.findall(r"@given\(", src))
    out["parametrize_decorators"] = len(re.findall(r"@pytest\.mark\.parametrize", src))
    return out


def grade_constitution(ws, py, tmp):
    fix = pristine("py-bloated-shop", os.path.join(tmp, "pristine"))
    out = {"src_unchanged": tree_hash(ws, "shop") == tree_hash(fix, "shop")}
    files = [os.path.relpath(os.path.join(d, f), ws) for d, dirs, fs in os.walk(ws)
             for f in fs if ".git" not in d.split(os.sep) and "__pycache__" not in d]
    out["new_files"] = sorted(set(files) - {os.path.relpath(os.path.join(d, f), fix)
                                           for d, dirs, fs in os.walk(fix) for f in fs if ".git" not in d.split(os.sep)})
    wf = "".join(open(os.path.join(ws, f)).read() for f in files if f.startswith(".github/workflows/"))
    out["ci_has_retry_loop"] = bool(re.search(r"for attempt in|--reruns|retry", wf))
    agent_md = "".join(open(os.path.join(ws, f)).read() for f in ("CLAUDE.md", "AGENTS.md") if os.path.exists(os.path.join(ws, f)))
    out["agent_instructions_chars"] = len(agent_md)
    out["pr_suite_still_passes"] = pytest_count(py, ws, respect_config=True)["exit"] == 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("workspace")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    ws = os.path.abspath(a.workspace)
    with tempfile.TemporaryDirectory(prefix="grade-") as tmp:
        if a.case in ("shop-audit", "shop-reduce"):
            res = grade_shop(a.case, ws, a.python, tmp)
        elif a.case == "loyalty-greenfield":
            res = grade_loyalty(ws, a.python, tmp)
        elif a.case == "constitution-setup":
            res = grade_constitution(ws, a.python, tmp)
        else:
            raise SystemExit(f"unknown case {a.case}")
    res["case"] = a.case
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
