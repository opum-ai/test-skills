"""Matrix-driven gate rules on synthetic matrices: tier floors, marginal value, triage, history, quarantine."""
import datetime as dt
import json

import pytest

from tmx import gate


def write(tmp_path, name, obj):
    (tmp_path / name).write_text(json.dumps(obj))
    return str(tmp_path / name)


def mut(file, status, killers, op="cmp", desc="< -> <=", line=1):
    return {"file": file, "line": line, "op": op, "desc": desc, "status": status, "killed_by": killers}


MATRIX = {"schema": "test-matrix/1", "tests": {"old": {}, "new_dup": {}, "new_good": {}}, "coverage": {},
          "mutants": {"a": mut("pay/x.py", "killed", ["old", "new_dup"]),
                      "b": mut("pay/x.py", "killed", ["new_good"], line=2),
                      "c": mut("pay/x.py", "survived", [], line=3),
                      "h": mut("pay/x.py", "survived", [], op="history", desc="revert abc: fix rounding", line=4),
                      "d": mut("util/y.py", "killed", ["old"])}}


@pytest.mark.parametrize("tier_rigor,triage,expected", [
    (None, {}, {"require_unique_kill"}),                                  # R3: 2/4 = 50% but no floor set
    ("R4", {}, {"tier:pay", "triage_survivors", "require_unique_kill"}),
    ("R4", {"pay/x.py:3:cmp:< -> <=": {"verdict": "equivalent", "reason": "clamp"},
            "pay/x.py:4:history:revert abc: fix rounding": {"verdict": "equivalent", "reason": "x"}},
     {"tier:pay", "require_unique_kill"}),
    ("R5", {"pay/x.py:3:cmp:< -> <=": {"verdict": "equivalent", "reason": "clamp"}},
     {"tier:pay", "triage_survivors", "history_must_be_killed", "require_unique_kill", "approval"}),
])
def test_tier_rules_by_rigor(tmp_path, monkeypatch, tier_rigor, triage, expected):
    monkeypatch.delenv("TMX_PR_APPROVERS", raising=False)
    tier = {"name": "pay", "paths": ["pay/*"], **({"rigor": tier_rigor} if tier_rigor else {})}
    (tmp_path / "testing").mkdir()
    write(tmp_path, "testing/survivors.json", triage)
    write(tmp_path, ".test-baseline.json", {"tests": 1, "test_ids": ["old"], "id_source": "matrix"})
    policy = {"rigor": "R3", "adequacy": {"tier": [tier]}}
    res = gate.run(policy, root=str(tmp_path), matrix_path=write(tmp_path, "m.json", MATRIX))
    assert {v["rule"].split(":")[0] if not v["rule"].startswith("tier") else v["rule"] for v in res["violations"]} == expected
    assert [v["message"].split()[0] for v in res["violations"] if v["rule"] == "require_unique_kill"] == ["new_dup"]


@pytest.mark.parametrize("level,age,rule", [("R3", 3, None), ("R3", 30, "quarantine_days"),
                                            ("R4", 10, "quarantine_days"), ("R5", 0, "quarantine_blocks")])
def test_quarantine_windows(tmp_path, level, age, rule):
    since = (dt.date.today() - dt.timedelta(days=age)).isoformat()
    write(tmp_path, ".test-quarantine.json", [{"test": "t", "since": since}])
    res = gate.run({"rigor": level}, root=str(tmp_path))
    assert [v["rule"] for v in res["violations"] if v["rule"] != "approval"] == ([rule] if rule else [])


def test_budget_growth_needs_a_trailer_and_at_r4_an_approval(tmp_path, monkeypatch):
    junit = tmp_path / "r.xml"
    junit.write_text("<testsuite>" + "".join(f"<testcase classname='t' name='n{i}' time='0.1'/>" for i in range(5)) + "</testsuite>")
    write(tmp_path, ".test-baseline.json", {"tests": 1})
    pol = {"rigor": "R4", "budget": {"max_new_tests_per_pr": 2, "max_tests": 4}}
    monkeypatch.delenv("TMX_PR_APPROVERS", raising=False)
    rules = lambda body: [v["rule"] for v in gate.run(pol, root=str(tmp_path), junit=[str(junit)], pr_body=body)["violations"]]  # noqa: E731
    assert rules("") == ["max_tests", "max_new_tests_per_pr"]
    assert rules("Test-Budget: new module\n") == ["max_tests", "max_new_tests_per_pr"]   # R4: trailer alone is not enough
    monkeypatch.setenv("TMX_PR_APPROVERS", "alice")
    assert rules("Test-Budget: new module\n") == ["max_tests"]


def test_demotion_must_be_certified_and_demoted_tests_still_count(tmp_path, monkeypatch):
    import subprocess
    g = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=tmp_path,  # noqa: E731
                                  check=True, capture_output=True)
    write(tmp_path, ".test-probation.json", [])
    g("init", "-q", "-b", "main")
    g("add", "-A")
    g("commit", "-qm", "base")
    g("checkout", "-qb", "pr")
    # new_good is the only killer of mutant b: demoting it would lose that kill.
    write(tmp_path, ".test-probation.json", [{"test": "new_good", "since": "2026-01-01"}])
    g("add", "-A")
    g("commit", "-qm", "demote")
    m = write(tmp_path, "m.json", MATRIX)
    res = gate.run({"rigor": "R3"}, root=str(tmp_path), matrix_path=m, base="main")
    assert "uncertified_demotion" in {v["rule"] for v in res["violations"]}
    junit = tmp_path / "r.xml"
    junit.write_text("<testsuite><testcase classname='t' name='a'/></testsuite>")
    res = gate.run({"rigor": "R3", "budget": {"max_tests": 1}}, root=str(tmp_path), junit=[str(junit)])
    assert "max_tests" in {v["rule"] for v in res["violations"]}      # 1 run + 1 demoted > 1


def test_future_dated_quarantine_is_rejected(tmp_path):
    future = (dt.date.today() + dt.timedelta(days=400)).isoformat()
    write(tmp_path, ".test-quarantine.json", [{"test": "t", "since": future}])
    assert [v["rule"] for v in gate.run({"rigor": "R3"}, root=str(tmp_path))["violations"]] == ["quarantine_date"]


def test_a_zero_mock_limit_is_enforced_not_ignored():
    from tmx import rigor
    assert rigor.rules("R4", {"admission": {"max_mocks_per_test": 0}})["max_mocks_per_test"] == 0
    assert rigor.rules("R4", {"flaky": {"quarantine_days": 30}, "probation": {"days": 1}})["quarantine_days"] == 7
    assert rigor.rules("R4", {"probation": {"days": 1, "min_nightly_runs": 1}})["probation_days"] == 30


def test_protection_is_by_exact_id_from_the_protected_file_not_by_name(tmp_path, monkeypatch):
    (tmp_path / "testing").mkdir()
    (tmp_path / "testing" / "protected.txt").write_text("# real-bug regressions\nnew_good\n")
    write(tmp_path, ".test-baseline.json", {"tests": 1, "test_ids": ["old"], "id_source": "matrix"})
    policy = {"rigor": "R3", "admission": {"protected_file": "testing/protected.txt"}}
    res = gate.run(policy, root=str(tmp_path), matrix_path=write(tmp_path, "m.json", MATRIX))
    weak = [v["message"].split()[0] for v in res["violations"] if v["rule"] == "require_unique_kill"]
    assert weak == ["new_dup"]      # new_dup is still judged; only the listed id is exempt
