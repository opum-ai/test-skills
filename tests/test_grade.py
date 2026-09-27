"""Regression test for the eval grader (evals/grade.py)."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("grade", os.path.join(HERE, "..", "evals", "grade.py"))
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


def test_clearing_addopts_keeps_the_projects_import_mode(tmp_path):
    # Past bug (plugin eval run 2026-09-26): a reduction that moved the originals to tests/probation/
    # relied on --import-mode=importlib in addopts; the grader cleared addopts and reported 6
    # collection errors for a suite that passes.
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-q --import-mode=importlib"\n')
    for d in ("tests", "tests/probation"):
        (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / d / "test_cart.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n")
    r = grade.pytest_count(sys.executable, str(tmp_path))
    assert (r["passed"], r["errors"]) == (2, 0), r["summary"]
