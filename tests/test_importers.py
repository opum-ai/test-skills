"""Stryker and PIT reports become the same test matrix; mutation_score reads it the same way."""
import json

from tmx import importers, matrix

STRYKER = {"files": {"src/a.ts": {"mutants": [
    {"id": "1", "mutatorName": "EqualityOperator", "replacement": "<=", "status": "Killed",
     "killedBy": ["t1"], "coveredBy": ["t1", "t2"], "location": {"start": {"line": 3}}},
    {"id": "2", "mutatorName": "BooleanLiteral", "status": "Survived", "coveredBy": ["t2"],
     "location": {"start": {"line": 5}}},
    {"id": "3", "status": "NoCoverage", "location": {"start": {"line": 9}}}]}},
    "testFiles": {"test/a.spec.ts": {"tests": [{"id": "t1", "name": "caps"}, {"id": "t2", "name": "adds"}]}}}
PIT = """<mutations>
<mutation detected='true' status='KILLED'><sourceFile>A.java</sourceFile><mutatedClass>com.x.A</mutatedClass>
<lineNumber>7</lineNumber><mutator>org.pitest.ConditionalsBoundaryMutator</mutator>
<killingTests>com.x.ATest.one()|com.x.ATest.two()</killingTests><succeedingTests></succeedingTests></mutation>
<mutation detected='false' status='SURVIVED'><sourceFile>A.java</sourceFile><mutatedClass>com.x.A</mutatedClass>
<lineNumber>9</lineNumber><mutator>org.pitest.MathMutator</mutator><killingTests/>
<succeedingTests>com.x.ATest.one()</succeedingTests></mutation>
</mutations>"""


def test_stryker_and_pit_reports_import_to_equivalent_matrices(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps(STRYKER))
    (tmp_path / "p.xml").write_text(PIT)
    importers.stryker(str(tmp_path / "s.json"), str(tmp_path / "ms.json"))
    importers.pit(str(tmp_path / "p.xml"), str(tmp_path / "mp.json"))
    s, p = matrix.load(str(tmp_path / "ms.json")), matrix.load(str(tmp_path / "mp.json"))
    assert sorted(mu["status"] for mu in s["mutants"].values()) == ["killed", "no_coverage", "survived"]
    assert [mu["killed_by"] for mu in s["mutants"].values() if mu["status"] == "killed"] == [["test/a.spec.ts::caps"]]
    assert matrix.mutation_score(s)["score"] == 1 / 3
    assert {mu["file"] for mu in p["mutants"].values()} == {"com/x/A.java"}
    assert matrix.mutation_score(p) == {"mutants": 2, "killed": 1, "timeout": 0, "score": 0.5}
    assert matrix.obligations(p) == {"mutant:pit00000": {"com.x.ATest.one()", "com.x.ATest.two()"}}


def test_subsumes_reports_exactly_the_kills_a_property_misses(tmp_path):
    import subprocess
    import sys
    import os
    tmx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "test-audit", "scripts", "tmx.py")
    m = {"schema": "test-matrix/1", "tests": {"prop": {}, "ex1": {}, "ex2": {}}, "coverage": {},
         "mutants": {"a": {"file": "f.py", "line": 1, "op": "cmp", "desc": "x", "status": "killed", "killed_by": ["prop", "ex1"]},
                     "b": {"file": "f.py", "line": 2, "op": "cmp", "desc": "y", "status": "killed", "killed_by": ["ex2"]}}}
    (tmp_path / "m.json").write_text(json.dumps(m))
    run = lambda *a: subprocess.run([sys.executable, tmx, "subsumes", "m.json", *a], cwd=tmp_path, capture_output=True, text=True)  # noqa: E731
    ok, bad = run("--by", "prop", "--tests", "ex1"), run("--by", "prop", "--tests", "ex*")
    assert ok.returncode == 0 and '"SUBSUMED"' in ok.stdout
    assert bad.returncode == 3 and "f.py:2 cmp y" in bad.stdout


def test_score_and_baseline_report_what_the_matrix_says(tmp_path):
    import subprocess
    import sys
    import os
    tmx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "test-audit", "scripts", "tmx.py")
    m = {"schema": "test-matrix/1", "tests": {"t1": {"duration": 0.5}, "t2": {"duration": 0.25}}, "coverage": {},
         "mutants": {"a": {"file": "f.py", "line": 1, "op": "cmp", "desc": "x", "status": "killed", "killed_by": ["t1"], "key": "f.py:1:cmp:x#1"},
                     "b": {"file": "f.py", "line": 2, "op": "cmp", "desc": "y", "status": "survived", "killed_by": [], "key": "f.py:2:cmp:y#1"},
                     "c": {"file": "f.py", "line": 3, "op": "cmp", "desc": "z", "status": "timeout", "killed_by": []}}}
    (tmp_path / "m.json").write_text(json.dumps(m))
    r = subprocess.run([sys.executable, tmx, "score", "m.json", "--survivors"], cwd=tmp_path, capture_output=True, text=True)
    s = json.loads(r.stdout[:r.stdout.rindex("}") + 1])
    assert s["mutation"] == {"mutants": 3, "killed": 2, "timeout": 1, "score": 2 / 3} and s["zero_kill_tests"] == 1
    assert "survived     f.py:2:cmp:y#1" in r.stdout and s["duration_s"] == 0.75
    r = subprocess.run([sys.executable, tmx, "baseline", "--matrix", "m.json"], cwd=tmp_path, capture_output=True, text=True)
    b = json.loads((tmp_path / ".test-baseline.json").read_text())
    assert r.returncode == 0 and b["tests"] == 2 and b["id_source"] == "matrix" and b["test_ids"] == ["t1", "t2"]
