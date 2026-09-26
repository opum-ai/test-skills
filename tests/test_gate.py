"""The gate end to end on a throwaway git repo: budget, smells, rigor levels, approvals."""
import json
import os
import subprocess
import sys

import pytest

from tmx import gate, rigor

TMX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "skills", "test-audit", "scripts", "tmx.py")
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


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert 1 + 1 == 2\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    git(tmp_path, "checkout", "-qb", "pr")
    with open(tmp_path / "tests" / "test_a.py", "a") as f:
        f.write("def test_b():\n    run()\n")
    git(tmp_path, "commit", "-qam", "add test")
    return tmp_path


@pytest.mark.parametrize("level,env,expected_rules,passed", [
    ("R1", {}, {"smell:no-assertion"}, True),                       # advisory: reported, not blocking
    ("R3", {}, {"smell:no-assertion"}, False),
    ("R5", {}, {"smell:no-assertion", "approval"}, False),          # no approval evidence at all
    ("R5", {"TMX_PR_APPROVERS": "mallory"}, {"smell:no-assertion", "approval"}, False),
    ("R5", {"TMX_PR_APPROVERS": "alice"}, {"smell:no-assertion"}, False),
])
def test_rigor_levels(repo, monkeypatch, level, env, expected_rules, passed):
    monkeypatch.delenv("TMX_PR_APPROVERS", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    res = gate.run(gate.mini_toml(POLICY.format(level=level)), root=str(repo), base="main")
    assert {v["rule"] for v in res["violations"]} == expected_rules and res["passed"] is passed


def test_a_trailer_raises_rigor_but_cannot_lower_it():
    assert rigor.highest(["R3", rigor.declared("Rigor: R4\n")]) == "R4"
    assert rigor.highest(["R4", rigor.declared("Rigor: R1\n")]) == "R4"
    assert rigor.rules("R5", {"admission": {"max_mocks_per_test": 9, "forbid_smells": []}})["max_mocks_per_test"] == 2


def test_mini_toml_matches_tomllib_on_the_shipped_template():
    tomllib = pytest.importorskip("tomllib")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    text = open(os.path.join(root, "skills", "test-constitution", "assets", "test-policy.toml")).read()
    text = (text.replace("{{critical_paths}}", '["a/**"]').replace("{{max_tests}}", "10")
            .replace("{{max_seconds}}", "60").replace("{{src}}", "pkg").replace("{{rigor}}", "R3")
            .replace("{{critical_rigor}}", "R4"))
    assert gate.mini_toml(text) == tomllib.loads(text)


def test_unknown_base_ref_is_a_usage_error(repo):
    (repo / "test-policy.toml").write_text(POLICY.format(level="R3"))
    r = subprocess.run([sys.executable, TMX, "gate", "--policy", "test-policy.toml", "--base", "nope"],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 2 and "not found" in r.stdout


def test_a_change_cannot_loosen_its_own_gate(repo):
    # Base policy allows 1 new test; the PR adds 2 and rewrites the policy to allow 99.
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    (repo / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (repo / ".test-baseline.json").write_text(json.dumps({"tests": 1}))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "adopt")
    git(repo, "checkout", "-q", "-b", "pr2")
    (repo / "test-policy.toml").write_text(POLICY.format(level="R3").replace("max_new_tests_per_pr = 1", "max_new_tests_per_pr = 99"))
    (repo / ".test-baseline.json").write_text(json.dumps({"tests": 3}))
    junit = repo / "r.xml"
    junit.write_text("<testsuite>" + "".join(f"<testcase classname='t' name='n{i}'/>" for i in range(3)) + "</testsuite>")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "loosen")
    r = subprocess.run([sys.executable, TMX, "gate", "--policy", "test-policy.toml", "--junit", "r.xml", "--base", "main"],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 1 and "max_new_tests_per_pr" in r.stdout and '"policy_source": "base"' in r.stdout


def test_adding_only_a_skip_decorator_to_an_existing_test_is_caught(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert 1 + 1 == 2\n")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "tests" / "test_a.py").write_text("import pytest\n\n\n@pytest.mark.skip('flaky')\ndef test_a():\n    assert 1 + 1 == 2\n")
    git(tmp_path, "commit", "-qam", "skip it")
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path), base="main")
    assert "smell:skipped" in {v["rule"] for v in res["violations"]}
