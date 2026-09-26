"""Audit -> reduce lifecycle on a real pytest project: collect, analyze, verify, probation,
prune, re-collect, compare. The one slow test; it is the end-to-end evidence for ADR-0002/0003."""
import json
import os
import shutil
import subprocess
import sys

import pytest

pytest.importorskip("coverage")
pytestmark = pytest.mark.slow   # nested real mutation runs: nightly tier (Article X)
TMX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "skills", "test-audit", "scripts", "tmx.py")
SRC = '''LIMIT = 100


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def discount(total, member):
    rate = 0.1 if member else 0.0
    if total >= LIMIT:
        rate += 0.05
    return round(total * (1 - rate), 2)
'''
TESTS = '''from calc import clamp, discount


def test_low(): assert clamp(-1, 0, 10) == 0
def test_low_again(): assert clamp(-5, 0, 10) == 0
def test_high(): assert clamp(11, 0, 10) == 10
def test_mid(): assert clamp(5, 0, 10) == 5
def test_runs(): clamp(3, 0, 10)
def test_member(): assert discount(50, True) == 45.0
def test_threshold(): assert discount(100, False) == 95.0
def test_below_threshold(): assert discount(99, False) == 99.0
def test_stacked(): assert discount(200, True) == 170.0
'''


def tmx(cwd, *args):
    r = subprocess.run([sys.executable, TMX, *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout


def test_certified_reduction_loses_no_kill_end_to_end(tmp_path):
    (tmp_path / "calc").mkdir()
    (tmp_path / "calc" / "__init__.py").write_text(SRC)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(TESTS)
    assert tmx(tmp_path, "collect-pytest", "--src", "calc", "--tests", "tests", "-o", ".tmx/m.json", "--jobs", "2")[0] == 0
    m = json.loads((tmp_path / ".tmx" / "m.json").read_text())
    limit = [mu for mu in m["mutants"].values() if mu["line"] == 1]
    assert limit and all(mu["status"] == "killed" for mu in limit)   # import-time constants are credited

    code, out = tmx(tmp_path, "analyze", ".tmx/m.json", "-o", ".tmx/p.json")
    plan = json.loads((tmp_path / ".tmx" / "p.json").read_text())
    assert code == 0 and plan["optimal"] and len(plan["keep"]) < 9
    assert plan["remove"]["tests/test_calc.py::test_runs"]["reason"] == "zero-signal"
    assert tmx(tmp_path, "verify", ".tmx/p.json", ".tmx/m.json")[0] == 0

    assert tmx(tmp_path, "probation", "add", "--plan", ".tmx/p.json")[0] == 0
    assert tmx(tmp_path, "probation", "install")[0] == 0
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", "not probation", "--junitxml=n.xml"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0 and f"{len(plan['keep'])} passed" in r.stdout
    subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml=n.xml"], cwd=tmp_path, capture_output=True)
    assert tmx(tmp_path, "probation", "record", "--junit", "n.xml")[0] == 0
    assert tmx(tmp_path, "probation", "prune", "--days", "0", "--min-runs", "1")[0] == 0

    assert tmx(tmp_path, "collect-pytest", "--src", "calc", "--tests", "tests", "-o", ".tmx/after.json")[0] == 0
    code, out = tmx(tmp_path, "compare", ".tmx/m.json", ".tmx/after.json")
    assert code == 0 and json.loads(out)["lost"] == [] and json.loads(out)["tests_after"] == len(plan["keep"])
