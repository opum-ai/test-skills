"""The Stryker path on REAL reports from evals/fixtures/ts-bloated-cart (Stryker 10, vitest-runner):
full = disableBail; bail = Stryker's default; vacuous = the same suite under vitest 5, where mutants
never reach the code (6.5% vs 97.4%). Each shape must be handled the way a reduction needs."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TMX = os.path.join(os.path.dirname(HERE), "skills", "test-audit", "scripts", "tmx.py")
DATA = os.path.join(HERE, "data", "stryker")


def tmx(cwd, *args):
    r = subprocess.run([sys.executable, TMX, *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout


def test_a_real_full_report_certifies_a_reduction_that_keeps_the_boundary_tests(tmp_path):
    assert tmx(tmp_path, "import-stryker", os.path.join(DATA, "full.json"), "-o", "m.json")[0] == 0
    m = json.loads((tmp_path / "m.json").read_text())
    keys = [mu["key"] for mu in m["mutants"].values()]
    assert len(m["tests"]) == 66 and len(keys) == len(set(keys))
    assert tmx(tmp_path, "analyze", "m.json", "-o", "p.json")[0] == 0
    keep = json.loads((tmp_path / "p.json").read_text())["keep"]
    assert "test/pricing.test.ts::volumeDiscountBps tier boundaries are inclusive" in keep and len(keep) < 20
    assert tmx(tmp_path, "verify", "p.json", "m.json")[0] == 0


@pytest.mark.parametrize("report,flag,why", [
    ("bail.json", "--allow-bail", "disableBail"),
    ("vacuous.json", "--allow-low-score", "never reaching the code"),
])
def test_reports_that_would_mislead_a_reduction_are_refused(tmp_path, report, flag, why):
    code, out = tmx(tmp_path, "import-stryker", os.path.join(DATA, report), "-o", "m.json")
    assert code == 4 and why in out and not (tmp_path / "m.json").exists()
    assert tmx(tmp_path, "import-stryker", os.path.join(DATA, report), "-o", "m.json", flag)[0] == 0


def test_js_smells_on_the_typescript_fixture():
    from tmx import smells
    root = os.path.join(os.path.dirname(HERE), "evals", "fixtures", "ts-bloated-cart", "test")
    found = {(i["smell"], i["test"].split("::")[1]) for f in sorted(os.listdir(root))
             for i in smells.js_smells(os.path.join(root, f))}
    assert found == {
        ("weak-assertion", "discount is a number"), ("weak-assertion", "result is not null"),
        ("weak-assertion", "returns a number"), ("implementation-coupled", "stores lines in a Map"),
        ("implementation-coupled", "calls percentOf exactly once"), ("mocks", "calls percentOf exactly once"),
        ("no-assertion", "remove of unknown sku is fine"), ("no-assertion", "does not crash for a normal line"),
        ("no-assertion", "flaky: add many items quickly"), ("skipped", "flaky: add many items quickly"),
        ("snapshot", "matches the snapshot"), ("sleep", "subtotal is stable after a short wait"),
        ("tautology", "always passes")}
