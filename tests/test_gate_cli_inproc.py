"""Drive the gate CLI in-process (TS-11).

The existing CLI tests shell out to tmx.py; a subprocess is invisible to the
per-test coverage the matrix collects, so the report/exit path in gate.main and
gate.write_baseline read as uncovered mutants. These call them directly so the
coverage (and so the kill matrix) can see them. Assertions are on observable
behaviour: exit codes, printed verdicts and the baseline file.
"""
import argparse
import json
import subprocess

from tmx import gate

POLICY = '''version = 1
rigor = "{level}"
[budget]
max_tests = 50
max_new_tests_per_pr = 1
[[adequacy.tier]]
name = "critical"
paths = ["pkg/*"]
[assurance]
approvers = ["alice"]
'''


def git(cwd, *a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True,
                   capture_output=True)


def make_repo(tmp_path, added):
    """A git repo on main, checked out to a branch that adds one test named by `added`."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert 1 + 1 == 2\n")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    git(tmp_path, "checkout", "-qb", "pr")
    with open(tmp_path / "tests" / "test_a.py", "a") as f:
        f.write(added)
    git(tmp_path, "commit", "-qam", "add a test")
    return tmp_path


def ns(repo, **over):
    base = dict(policy=str(repo / "test-policy.toml"), policy_source=None, base="main",
                root=str(repo), junit=None, matrix=None, json=False)
    base.update(over)
    return argparse.Namespace(**base)


def test_gate_cli_prints_each_violation_and_returns_one(tmp_path, capsys):
    repo = make_repo(tmp_path, "def test_b():\n    run()\n")   # added with no assertion, R3 blocks
    assert gate.main(ns(repo)) == 1
    out = capsys.readouterr().out
    assert "FAIL Art. IV smell:no-assertion" in out and "violation(s)" in out


def test_gate_cli_json_mode_prints_the_envelope_and_returns_one(tmp_path, capsys):
    repo = make_repo(tmp_path, "def test_b():\n    run()\n")
    assert gate.main(ns(repo, json=True)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False and payload["violations"]


def test_gate_cli_is_zero_when_nothing_is_wrong(tmp_path, capsys):
    repo = make_repo(tmp_path, "def test_b():\n    assert 2 + 2 == 4\n")
    assert gate.main(ns(repo)) == 0
    assert "PASS" in capsys.readouterr().out


def test_gate_cli_missing_policy_is_a_usage_exit(tmp_path, capsys):
    repo = make_repo(tmp_path, "def test_b():\n    assert 2 + 2 == 4\n")
    (repo / "test-policy.toml").unlink()
    assert gate.main(ns(repo, base=None)) == 2
    assert "no policy" in capsys.readouterr().out


def test_write_baseline_records_junit_totals_and_ids(tmp_path):
    repo = make_repo(tmp_path, "def test_b():\n    assert 2 + 2 == 4\n")
    junit = repo / "r.xml"
    junit.write_text("<testsuite><testcase classname='t' name='n0'/><testcase classname='t' name='n1'/>"
                     "<testcase classname='t' name='n2'><skipped/></testcase></testsuite>")
    b = gate.write_baseline(str(repo), ".test-baseline.json", junit=[str(junit)])
    assert b["tests"] == 3 and b["hidden_tests"] == 0 and b["id_source"] == "junit"
    assert json.loads((repo / ".test-baseline.json").read_text())["tests"] == 3


def test_write_baseline_prefers_a_matrix_and_records_its_score(tmp_path):
    repo = make_repo(tmp_path, "def test_b():\n    assert 2 + 2 == 4\n")
    m = {"schema": "test-matrix/1", "tests": {"a::test_a": {"duration": 0.5}},
         "mutants": {"m1": {"file": "pkg/x.py", "line": 1, "op": "const", "desc": "1 -> 0",
                            "status": "killed", "killed_by": ["a::test_a"]}}}
    mp = repo / "m.json"
    mp.write_text(json.dumps(m))
    b = gate.write_baseline(str(repo), ".test-baseline.json", matrix_path=str(mp))
    assert b["id_source"] == "matrix" and b["tests"] == 1 and b["mutation"]["killed"] == 1
