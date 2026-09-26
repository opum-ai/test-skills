"""Regression tests for the soundness findings of the engine review (2026-09-26). Each builds the
reviewer's scenario on a tiny real pytest project and asserts the engine no longer certifies a
loss or deletes kept code. Slow-ish (real mutant runs); they are the evidence for ADR-0002/0003."""
import json
import os
import subprocess
import sys

import pytest

from tmx import probation

pytest.importorskip("coverage")
pytestmark = pytest.mark.slow   # nested real mutation runs: nightly tier (Article X)
TMX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "skills", "test-audit", "scripts", "tmx.py")


def project(tmp_path, src, tests):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text(src)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_p.py").write_text(tests)
    return tmp_path


def tmx(cwd, *args):
    r = subprocess.run([sys.executable, TMX, *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def collect(p):
    code, out = tmx(p, "collect-pytest", "--src", "pkg", "--tests", "tests", "-o", ".tmx/m.json", "--jobs", "2")
    assert code == 0, out
    return json.loads((p / ".tmx" / "m.json").read_text())


def test_a_killer_that_shares_a_module_fixture_is_credited(tmp_path):
    # The fixture body runs during test_first's setup only, so coverage credits its lines to
    # test_first; test_second (the real checker) must still be found by the full-suite confirmation.
    p = project(tmp_path, "def make_table():\n    return {'k': 1 + 1}\n",
                "import pytest\nfrom pkg import make_table\n\n\n@pytest.fixture(scope='module')\n"
                "def table():\n    return make_table()\n\n\ndef test_first(table):\n    assert 'k' in table\n\n\n"
                "def test_second(table):\n    assert table['k'] == 2\n")
    m = collect(p)
    arith = [mu for mu in m["mutants"].values() if mu["op"] == "arith"]
    assert arith and all("tests/test_p.py::test_second" in mu["killed_by"] for mu in arith)
    assert tmx(p, "analyze", ".tmx/m.json", "-o", ".tmx/p.json")[0] == 0
    assert "tests/test_p.py::test_second" in json.loads((p / ".tmx" / "p.json").read_text())["keep"]


def test_order_dependent_false_kills_are_caught_by_the_empirical_rerun(tmp_path):
    # test_c_weak only passes after test_a has run; in subset runs it "fails" and looks like a killer.
    p = project(tmp_path, "STATE = {}\n\n\ndef double(x):\n    return x * 2\n",
                "from pkg import STATE, double\n\n\ndef test_a():\n    STATE['ready'] = True\n    assert double(2) == 4\n\n\n"
                "def test_c_weak():\n    assert STATE.get('ready')\n    double(3)\n")
    collect(p)
    code, out = tmx(p, "analyze", ".tmx/m.json", "-o", ".tmx/p.json")
    code, out = tmx(p, "verify", ".tmx/p.json", ".tmx/m.json", "--rerun", "--jobs", "2")
    plan = json.loads((p / ".tmx" / "p.json").read_text())
    if plan["keep"] == ["tests/test_p.py::test_c_weak"]:
        assert code == 3 and "INVALID" in out          # the bogus certificate is refused
    else:
        assert code == 0 and "replayed" in out          # or the plan never relied on it


def test_a_hang_is_attributed_to_the_test_that_hangs(tmp_path):
    p = project(tmp_path, "def count_to(n):\n    i = 0\n    while i != n:\n        i += 1\n    return i\n",
                "from pkg import count_to\n\n\ndef test_zero():\n    assert count_to(0) == 0\n\n\n"
                "def test_three():\n    assert count_to(3) == 3\n")
    m = collect(p)
    hang = [mu for mu in m["mutants"].values() if mu["desc"] == "+= -> -="]
    assert hang and hang[0]["status"] == "killed" and hang[0]["killed_by"] == ["tests/test_p.py::test_three"]


def test_an_empty_matrix_never_certifies_deleting_everything(tmp_path):
    p = project(tmp_path, "def f():\n    return 1\n", "from pkg import f\n\n\ndef test_f():\n    assert f() == 1\n")
    assert tmx(p, "collect-pytest", "--src", "pkg", "--tests", "tests", "-o", ".tmx/m.json", "--no-mutate")[0] == 0
    code, out = tmx(p, "analyze", ".tmx/m.json", "-o", ".tmx/p.json")
    assert code == 2 and "no obligations" in out


def test_chained_comparisons_get_distinct_mutant_keys(tmp_path):
    p = project(tmp_path, "def ok(x):\n    return 0 <= x <= 10\n",
                "from pkg import ok\n\n\ndef test_low():\n    assert not ok(-1) and ok(0)\n\n\n"
                "def test_high():\n    assert ok(10) and not ok(11)\n")
    m = collect(p)
    keys = [mu["key"] for mu in m["mutants"].values()]
    assert len(keys) == len(set(keys)) and any(k.endswith("#2") for k in keys)


def test_prune_keeps_a_stacked_parametrize_table_with_retained_cases(tmp_path):
    (tmp_path / "tests").mkdir()
    src = ("import pytest\nX = 'a\x0cb'   # a form feed must not shift line numbers\n\n\n"
           "@pytest.mark.parametrize('a', [1, 2])\n@pytest.mark.parametrize('b', [10, 20])\n"
           "def test_grid(a, b):\n    assert a * b\n\n\ndef test_drop():\n    assert 1\n\n\ndef test_keep():\n    assert 2\n")
    f = tmp_path / "tests" / "test_g.py"
    f.write_text(src)
    entries = [{"test": t, "since": "2026-01-01", "reason": "subsumed", "witness": [], "runs": 5, "failures": 0,
                "last_run": None} for t in ["tests/test_g.py::test_grid[10-1]", "tests/test_g.py::test_drop"]]
    (tmp_path / ".test-probation.json").write_text(json.dumps(entries))
    collected = probation.collected_ids(str(tmp_path), sys.executable)
    r = probation.prune(str(tmp_path), str(tmp_path / ".test-probation.json"), 0, 1, collected=collected)
    text = f.read_text()
    assert r["deleted"] == ["tests/test_g.py::test_drop"] and "tests/test_g.py::test_grid" in r["partial_tables"]
    assert "def test_grid" in text and "def test_keep():\n    assert 2" in text and "test_drop" not in text
    assert "a\x0cb" in text


def test_a_broken_harness_cannot_pass_off_as_a_perfect_score(tmp_path):
    # Originally mutant runs ignored --tests, collected this broken file, and every collection
    # error was counted as a kill: a vacuous 100%. Now runs honor --tests, and a control run
    # must be green before any mutant is judged.
    p = project(tmp_path, "def inc(x):\n    return x + 1\n", "from pkg import inc\n\n\ndef test_inc():\n    assert inc(1) == 2\n")
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "test_broken.py").write_text("import does_not_exist\n")
    m = collect(p)
    assert not any("collection error" in mu.get("note", "") for mu in m["mutants"].values())
    assert {mu["status"] for mu in m["mutants"].values()} <= {"killed", "survived", "timeout"}
