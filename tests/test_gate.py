"""The gate end to end on a throwaway git repo: budget, smells, rigor levels, approvals."""
import datetime as dt
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
    # An unrecognised level is a usage error, not something silently normalised to a default.
    with pytest.raises(SystemExit):
        rigor.norm("R9")


def test_a_trailer_raises_rigor_but_cannot_lower_it():
    assert rigor.highest(["R3", rigor.declared("Rigor: R4\n")]) == "R4"
    assert rigor.highest(["R4", rigor.declared("Rigor: R1\n")]) == "R4"
    assert rigor.rules("R5", {"admission": {"max_mocks_per_test": 9, "forbid_smells": []}})["max_mocks_per_test"] == 2


def test_mini_toml_parses_the_shipped_template_on_every_supported_python():
    try:
        import tomllib
    except ImportError:   # Python < 3.11: the fallback parser is what runs in production there
        tomllib = None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    text = open(os.path.join(root, "skills", "test-constitution", "assets", "test-policy.toml")).read()
    text = (text.replace("{{critical_paths}}", '["a/**"]').replace("{{max_tests}}", "10")
            .replace("{{max_seconds}}", "60").replace("{{src}}", "pkg").replace("{{rigor}}", "R3")
            .replace("{{critical_rigor}}", "R4"))
    got = gate.mini_toml(text)
    assert got["rigor"] == "R3" and got["budget"]["max_tests"] == 10 and got["test_roots"] == ["tests"]
    assert [t["name"] for t in got["adequacy"]["tier"]] == ["critical", "standard", "glue"]
    assert got["adequacy"]["tier"][0] == {"name": "critical", "paths": ["a/**"], "rigor": "R4", "min_mutation_score": 0.8}
    assert "sleep" in got["admission"]["forbid_smells"] and got["flaky"]["max_skipped"] == 0
    assert tomllib is None or got == tomllib.loads(text)
    # Nested values, which the shipped template has none of: a list inside a list exercises the
    # depth counter, a table exercises the value parser's dict arm, and a bare word is a usage
    # error rather than something silently parsed.
    nested = gate.mini_toml('a = [["x"], ["y"]]\nb = {k = 1, j = 2}\n')
    assert nested == {"a": [["x"], ["y"]], "b": {"k": 1, "j": 2}}
    assert tomllib is None or nested == tomllib.loads('a = [["x"], ["y"]]\nb = {k = 1, j = 2}\n')
    with pytest.raises(SystemExit):
        gate.mini_toml("bad = nonsense\n")


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
    # Real node ids: the gate measures the base tree's own collection, so a fabricated classname
    # would read as a baseline that no longer describes the base rather than as the growth it is.
    junit.write_text("<testsuite>" + "".join(f"<testcase classname='tests.test_a' name='test_{n}'/>"
                                             for n in "abc") + "</testsuite>")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "loosen")
    r = subprocess.run([sys.executable, TMX, "gate", "--policy", "test-policy.toml", "--junit", "r.xml", "--base", "main"],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 1 and "max_new_tests_per_pr" in r.stdout and '"policy_source": "base"' in r.stdout


def _junit(path, names):
    path.write_text("<testsuite>" + "".join(f"<testcase classname='tests.test_a' name='{n}' time='0.1'/>"
                                             for n in names) + "</testsuite>")


def test_a_baseline_that_matches_the_base_commits_measured_count_passes(tmp_path):
    # The base collects three ids: test_a and test_b are the PR tier, test_slow is deselected and absent
    # from both the run and the baseline. The PR deletes test_b and adds test_c. The baseline says 2, and
    # 2 is what the base contributes: the deselected test is scoped out, and the deleted one still counts
    # because the baseline lists it, so a reduction is not read as a stale baseline it could not repair.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert 1 + 1 == 2\n\n\ndef test_b():\n    assert 2 + 2 == 4\n"
        "\n\ndef test_slow():\n    assert 3 + 3 == 6\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert 1 + 1 == 2\n\n\ndef test_c():\n    assert 4 + 4 == 8\n"
        "\n\ndef test_slow():\n    assert 3 + 3 == 6\n")
    git(tmp_path, "commit", "-qam", "drop one, add one")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (tmp_path / ".test-baseline.json").write_text(json.dumps(
        {"tests": 2, "test_ids": ["tests.test_a::test_a", "tests.test_a::test_b"]}))
    junit = tmp_path / "r.xml"
    _junit(junit, ["test_a", "test_c"])
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path), junit=[str(junit)], base="main")
    assert res["info"]["baseline_measured"] == 2
    assert res["passed"] is True


@pytest.mark.parametrize("recorded", [0, 2])
def test_a_baseline_that_does_not_match_the_base_count_fails_by_name(repo, recorded):
    # 0 is the shipped bug (below the base's count); 2 is the same mismatch upwards. Both refuse.
    (repo / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (repo / ".test-baseline.json").write_text(json.dumps({"tests": recorded}))
    junit = repo / "r.xml"
    _junit(junit, ["test_a", "test_b"])
    sha = subprocess.run(["git", "rev-parse", "main"], cwd=repo, capture_output=True, text=True).stdout.strip()
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(repo), junit=[str(junit)], base="main")
    msg = [v["message"] for v in res["violations"] if v["rule"] == "stale_baseline"][0]
    assert f"says {recorded} tests" in msg and "runs 1" in msg     # both numbers
    assert sha in msg                                              # the base SHA
    assert "Article XIII" in msg and "only way" in msg             # the only way to move it
    assert res["passed"] is False


def test_an_unmeasurable_base_fails_the_baseline_check_rather_than_passing_it(tmp_path):
    # A PARTIAL collection is not a measurement either: the good file still prints ids, so a gate that
    # only looked for output would count a partial base as measured and compare against the wrong number.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_good.py").write_text("def test_ok():\n    assert 1 == 1\n")
    (tmp_path / "tests" / "test_broken.py").write_text("def test_x(:\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (tmp_path / ".test-baseline.json").write_text(json.dumps({"tests": 1}))
    junit = tmp_path / "r.xml"
    _junit(junit, ["test_a"])
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path), junit=[str(junit)], base="main")
    assert "baseline_unmeasured" in {v["rule"] for v in res["violations"]} and res["passed"] is False


def test_a_tree_with_no_pytest_suite_is_not_measured(tmp_path):
    # The check applies to pytest suites; another language's junit still drives the growth rules.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.test.js").write_text("test('a', () => expect(1).toBe(1));\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (tmp_path / ".test-baseline.json").write_text(json.dumps({"tests": 1}))
    junit = tmp_path / "r.xml"
    _junit(junit, ["test_a"])
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path), junit=[str(junit)], base="main")
    assert res["info"]["baseline_measured"] == "not-a-pytest-project"
    assert not any(v["rule"] in ("stale_baseline", "baseline_unmeasured") for v in res["violations"])


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


def _base_repo(tmp_path, files):
    """A repo whose `main` carries `files`, checked out on a `pr` branch with nothing changed yet."""
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    return tmp_path


def _commit(tmp_path, message):
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", message)


def _assert_corrupt_head_is_named_with_a_base(tmp_path, state_file, kind):
    """A corrupt HEAD state file fails by name whether the base is readable or corrupt too (DEC-213)."""
    for label, base_text in (("valid-base", "[]"), ("corrupt-base", "{not json")):
        repo = tmp_path / f"head-{kind}-{label}"
        repo.mkdir()
        _base_repo(repo, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n", state_file: base_text})
        (repo / state_file).write_text("{head not json")
        _commit(repo, "corrupt the head copy")
        res = gate.run({"rigor": "R3"}, root=str(repo), base="main")
        assert [v["rule"] for v in res["violations"]] == ["unreadable_state_file"]
        assert state_file in res["violations"][0]["message"] and kind in res["violations"][0]["message"]
        # The base is read on its own: a corrupt base copy is named and read as empty, a valid one is not.
        named = res["info"].get("unreadable_base_state_files", [])
        assert [state_file in line for line in named] == ([True] if label == "corrupt-base" else [])


def test_a_suite_slower_than_its_budget_is_flagged(tmp_path):
    # The budget compares the SUM of the report's durations. The policy also sets a per-change
    # growth limit while no baseline exists: a case with no baseline must not reach for one.
    junit = tmp_path / "r.xml"
    junit.write_text("<testsuite><testcase classname='t' name='a' time='30'/>"
                     "<testcase classname='t' name='b' time='30'/></testsuite>")
    pol = {"rigor": "R3", "budget": {"max_suite_seconds": 50, "max_new_tests_per_pr": 1}}
    res = gate.run(pol, root=str(tmp_path), junit=[str(junit)])
    assert [v["rule"] for v in res["violations"]] == ["max_suite_seconds"]
    assert res["violations"][0]["message"] == "suite takes 60.0s, budget 50s"
    assert gate.junit_totals([str(junit)])["seconds"] == 60.0


def test_a_skipped_test_over_the_limit_is_flagged(tmp_path):
    junit = tmp_path / "r.xml"
    pol = {"rigor": "R3", "flaky": {"max_skipped": 0}, "budget": {"max_new_tests_per_pr": 1}}
    junit.write_text("<testsuite><testcase classname='t' name='ok'/>"
                     "<testcase classname='t' name='skipped'><skipped/></testcase></testsuite>")
    res = gate.run(pol, root=str(tmp_path), junit=[str(junit)])
    assert [v["rule"] for v in res["violations"]] == ["max_skipped"]
    assert res["violations"][0]["message"] == "1 skipped tests, limit 0"
    junit.write_text("<testsuite><testcase classname='t' name='ok'/></testsuite>")
    assert gate.run(pol, root=str(tmp_path), junit=[str(junit)])["violations"] == []


def test_a_changed_test_with_too_many_mocks_is_flagged(tmp_path):
    # The limit is the profile's own 3, not something the policy has to repeat: three mocks are
    # at the limit and pass, four exceed it. Only the offending test is named.
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n"})
    (tmp_path / "tests" / "test_a.py").write_text(
        "from unittest.mock import Mock\n\n\n"
        "def test_at_the_limit():\n"
        "    a, b, c = Mock(), Mock(), Mock()\n"
        "    assert a.called is False and b.called is False and c.called is False\n\n\n"
        "def test_over_the_limit():\n"
        "    a, b, c, d = Mock(), Mock(), Mock(), Mock()\n"
        "    assert d.called is False\n")
    _commit(tmp_path, "add mock-heavy tests")
    res = gate.run({"rigor": "R3"}, root=str(tmp_path), base="main")
    msgs = [v["message"] for v in res["violations"] if v["rule"] == "max_mocks_per_test"]
    assert len(msgs) == 1
    assert "test_over_the_limit" in msgs[0] and "(limit 3 at R3)" in msgs[0]


def test_a_new_quarantine_entry_at_r4_needs_an_approver(tmp_path, monkeypatch):
    monkeypatch.delenv("TMX_PR_APPROVERS", raising=False)
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                          ".test-quarantine.json": "[]"})
    (tmp_path / ".test-quarantine.json").write_text(json.dumps(
        [{"test": "tests.test_a::test_a", "since": dt.date.today().isoformat(),
          "owner": "alice", "issue": "https://example.invalid/1"}]))
    _commit(tmp_path, "quarantine one")
    res = gate.run({"rigor": "R4"}, root=str(tmp_path), base="main")
    assert [v["rule"] for v in res["violations"]] == ["quarantine_entry"]
    assert "needs a listed approver" in res["violations"][0]["message"]
    # The same change at R3 is judged by the entry's own justification, not by an approver.
    assert gate.run({"rigor": "R3"}, root=str(tmp_path), base="main")["violations"] == []


def test_a_new_quarantine_entry_without_owner_and_issue_is_flagged(tmp_path):
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                          ".test-quarantine.json": "[]"})
    (tmp_path / ".test-quarantine.json").write_text(json.dumps(
        [{"test": "tests.test_a::test_a", "since": dt.date.today().isoformat()}]))
    _commit(tmp_path, "quarantine one with no justification")
    res = gate.run({"rigor": "R3"}, root=str(tmp_path), base="main")
    assert [v["rule"] for v in res["violations"]] == ["quarantine_entry"]
    assert "without an owner and an issue link" in res["violations"][0]["message"]
    # A base copy that will not parse is not a violation: it reads as empty, so every head entry
    # counts as newly added and the report names the unreadable file (DEC-213 (a2)).
    bad = tmp_path / "corrupt-base"
    bad.mkdir()
    _base_repo(bad, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                     ".test-quarantine.json": "{not json"})
    entry = [{"test": "tests.test_a::test_a", "since": dt.date.today().isoformat(),
              "owner": "alice", "issue": "https://example.invalid/1"}]
    (bad / ".test-quarantine.json").write_text(json.dumps(entry))
    _commit(bad, "quarantine one against a corrupt base")
    res = gate.run({"rigor": "R3"}, root=str(bad), base="main")
    assert res["violations"] == []
    assert any(".test-quarantine.json" in line and "newly added" in line
               for line in res["info"]["unreadable_base_state_files"])
    # Strip its justification and the same head entry is refused, so a corrupt base fails strict.
    entry[0].pop("owner")
    (bad / ".test-quarantine.json").write_text(json.dumps(entry))
    _commit(bad, "drop the owner")
    res = gate.run({"rigor": "R3"}, root=str(bad), base="main")
    assert [v["rule"] for v in res["violations"]] == ["quarantine_entry"]
    _assert_corrupt_head_is_named_with_a_base(tmp_path, ".test-quarantine.json", "quarantine")


def test_a_new_probation_entry_without_a_matrix_is_flagged(tmp_path):
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                          ".test-probation.json": "[]"})
    (tmp_path / ".test-probation.json").write_text(json.dumps(
        [{"test": "tests.test_a::test_a", "since": dt.date.today().isoformat()}]))
    _commit(tmp_path, "demote one")
    res = gate.run({"rigor": "R3"}, root=str(tmp_path), base="main")
    assert "uncertified_demotion" in {v["rule"] for v in res["violations"]}
    # A matrix is what certifies the demotion; supplying one clears the finding.
    m = {"schema": "test-matrix/1", "tests": {}, "coverage": {}, "mutants": {}}
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m))
    res = gate.run({"rigor": "R3"}, root=str(tmp_path), base="main", matrix_path=str(path))
    assert "uncertified_demotion" not in {v["rule"] for v in res["violations"]}
    # The same entry against a base whose probation file will not parse is still uncertified:
    # the base reads as empty, so the entry counts as newly added (DEC-213 (a2)).
    bad = tmp_path / "corrupt-base"
    bad.mkdir()
    _base_repo(bad, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                     ".test-probation.json": "{not json"})
    (bad / ".test-probation.json").write_text(json.dumps(
        [{"test": "tests.test_a::test_a", "since": dt.date.today().isoformat()}]))
    _commit(bad, "demote one against a corrupt base")
    res = gate.run({"rigor": "R3"}, root=str(bad), base="main")
    assert "uncertified_demotion" in {v["rule"] for v in res["violations"]}
    assert any(".test-probation.json" in line and "newly added" in line
               for line in res["info"]["unreadable_base_state_files"])
    # With a matrix supplied the same head is certified, so the corrupt base adds no violation and
    # the report still names the unreadable file.
    res = gate.run({"rigor": "R3"}, root=str(bad), base="main", matrix_path=str(path))
    assert res["violations"] == []
    assert any(".test-probation.json" in line and "newly added" in line
               for line in res["info"]["unreadable_base_state_files"])
    _assert_corrupt_head_is_named_with_a_base(tmp_path, ".test-probation.json", "probation")


def test_a_base_tree_that_drops_its_tests_cannot_be_measured(tmp_path):
    # The tracked tree promises a suite; `git archive` is told to leave it out. The measurement is
    # owed and cannot be taken, which is a failure — not the same thing as a tree with no suite.
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                          ".gitattributes": "tests/ export-ignore\n"})
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (tmp_path / ".test-baseline.json").write_text(json.dumps({"tests": 1}))
    junit = tmp_path / "r.xml"
    _junit(junit, ["test_a"])
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path),
                   junit=[str(junit)], base="main")
    assert "baseline_unmeasured" in {v["rule"] for v in res["violations"]}
    assert res["info"]["baseline_measured"] is None


def test_collected_ids_folds_a_class_into_the_module_part(tmp_path):
    # JUnit reports a nested class as classname mod.TestOuter.TestInner, so the base's collected
    # ids must fold at every level of nesting; a parametrized name keeps its own `::` inside the
    # brackets and must not be folded into the module. Either mistake leaves the measurement and
    # the run with no ids in common, and a correct baseline is refused as stale.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_n.py").write_text(
        "class TestOuter:\n    class TestInner:\n        def test_z(self):\n            assert 1 == 1\n")
    (tmp_path / "tests" / "test_p.py").write_text(
        "import pytest\n\n\n@pytest.mark.parametrize(\"x\", [\"a::b\"])\ndef test_p(x):\n"
        "    assert x == \"a::b\"\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    (tmp_path / ".test-baseline.json").write_text(json.dumps(
        {"tests": 2, "test_ids": ["tests.test_n.TestOuter.TestInner::test_z",
                                  "tests.test_p::test_p[a::b]"]}))
    junit = tmp_path / "r.xml"
    junit.write_text("<testsuite>"
                     "<testcase classname='tests.test_n.TestOuter.TestInner' name='test_z'/>"
                     "<testcase classname='tests.test_p' name='test_p[a::b]'/>"
                     "</testsuite>")
    res = gate.run(gate.mini_toml(POLICY.format(level="R3")), root=str(tmp_path),
                   junit=[str(junit)], base="main")
    assert res["info"]["baseline_measured"] == 2
    assert res["violations"] == []


def test_matrix_coverage_of_a_changed_test_scopes_the_tiers(tmp_path):
    # A changed test file counts as touching every source file it covers, so the matrix pulls the
    # critical tier (and its R4) into play even though only a test file changed.
    _base_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    assert 1 == 1\n",
                          "pkg/critical.py": "def f():\n    return 1\n"})
    (tmp_path / "tests" / "test_a.py").write_text(
        "from pkg.critical import f\n\n\ndef test_a():\n    assert f() == 1\n")
    _commit(tmp_path, "make the test cover the critical module")
    tiers = [{"name": "critical", "paths": ["pkg/*"], "rigor": "R4"}]
    m = {"schema": "test-matrix/1", "tests": {"tests/test_a.py::test_a": {}},
         "coverage": {"tests/test_a.py::test_a": ["pkg/critical.py:1"]}, "mutants": {}}
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m))
    res = gate.run({"rigor": "R3", "adequacy": {"tier": tiers}}, root=str(tmp_path),
                   base="main", matrix_path=str(path))
    assert res["info"]["rigor"] == "R4 Strict"
    # The tier matcher itself: first match wins, and a path outside every tier has none.
    assert gate._tier_of("pkg/critical.py", tiers)["name"] == "critical"
    assert gate._tier_of("other/x.py", tiers) is None


def test_edit_hook_judges_only_the_tests_an_edit_touched(tmp_path):
    hook = os.path.join(os.path.dirname(TMX), "..", "..", "test-constitution", "scripts", "hook_test_edit.py")
    (tmp_path / "test-policy.toml").write_text(POLICY.format(level="R3"))
    t = tmp_path / "test_x.py"
    t.write_text("def test_old_debt():\n    run()\n\n\ndef test_ok():\n    assert f() == 1\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    payload = json.dumps({"tool_input": {"file_path": str(t)}, "cwd": str(tmp_path)})
    run = lambda: subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True)  # noqa: E731
    t.write_text(t.read_text().replace("assert f() == 1", "assert f() == 1 and g() == 2"))
    assert run().returncode == 0                       # old no-assert debt is not blamed on this edit
    t.write_text(t.read_text() + "\n\ndef test_new():\n    h()\n")
    r = run()
    assert r.returncode == 2 and "test_new" in r.stderr and "test_old_debt" not in r.stderr
