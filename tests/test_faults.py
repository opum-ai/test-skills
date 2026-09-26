"""tmx faults: domain faults as text patches, any JUnit-writing command, exact attribution."""
import json
import os
import subprocess
import sys

TMX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "test-audit", "scripts", "tmx.py")


def test_faults_are_attributed_only_to_tests_that_really_catch_them(tmp_path):
    (tmp_path / "tax.py").write_text("RATES = {'NY': 400, 'OR': 0}\n\n\ndef tax(cents, region):\n    return cents * RATES[region] // 10000\n")
    (tmp_path / "test_tax.py").write_text("from tax import tax\n\n\ndef test_ny():\n    assert tax(10000, 'NY') == 400\n\n\n"
                                          "def test_or():\n    assert tax(10000, 'OR') == 0\n")
    faults = [{"file": "tax.py", "find": "'NY': 400", "replace": "'NY': 450", "desc": "wrong NY rate"},
              {"file": "tax.py", "find": "return cents", "replace": "return (cents", "desc": "breaks the import"},
              {"file": "tax.py", "find": "'TX': 625", "replace": "'TX': 600", "desc": "stale: not in the source"}]
    (tmp_path / "faults.json").write_text(json.dumps(faults))
    cmd = f"{sys.executable} -m pytest -q -p no:cacheprovider --junitxml={{junit}}"
    r = subprocess.run([sys.executable, TMX, "faults", "faults.json", "--cmd", cmd, "-o", "m.json", "--jobs", "2"],
                       cwd=tmp_path, capture_output=True, text=True)
    m = json.loads((tmp_path / "m.json").read_text())
    got = {mu["desc"]: (mu["status"], mu["killed_by"]) for mu in m["mutants"].values()}
    assert r.returncode == 0 and len(m["tests"]) == 2
    assert got["wrong NY rate"] == ("killed", ["test_tax::test_ny"])
    assert got["breaks the import"][0] == "error" and got["stale: not in the source"][0] == "error"
