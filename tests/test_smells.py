"""Smell detection: one table row per smell class the gate can enforce."""
import pytest

from tmx import smells

CASES = [
    ("def test_x():\n    f()\n", {"no-assertion"}),
    ("def test_x():\n    r = f()\n    assert r == r\n", {"tautology"}),
    ("def test_x():\n    assert isinstance(f(), int)\n", {"weak-assertion"}),
    ("import time\ndef test_x():\n    time.sleep(1)\n    assert f()\n", {"sleep"}),
    ("from unittest.mock import patch\ndef test_x():\n    with patch('pkg._a'), patch('pkg.b'), patch('pkg.c'):\n        assert f() == 1\n",
     {"mock-heavy", "implementation-coupled"}),
    ("def test_x():\n    try:\n        f()\n    except Exception:\n        pass\n    assert g() == 1\n", {"swallowed-exception"}),
    ("import pytest\n@pytest.mark.skip('flaky')\ndef test_x():\n    assert f() == 1\n", {"skipped"}),
    ("def test_x():\n    assert f(2) == 4\n", set()),
    # Not smells (false positives found in review): determinism, NaN, conditional skip, yielding sleep,
    # the test's own helper, namedtuple's public _replace.
    ("def test_x():\n    assert enc(d) == enc(d)\n", set()),
    ("def test_x():\n    r = nan()\n    assert r != r\n", set()),
    ("import sys, pytest\n@pytest.mark.skipif(sys.platform == 'win32', reason='posix')\ndef test_x():\n    assert f() == 1\n", set()),
    ("import asyncio\nasync def test_x():\n    await asyncio.sleep(0)\n    assert f() == 1\n", set()),
    ("class TestA:\n    def _rt(self):\n        return 1\n    def test_x(self):\n        assert self._rt() == 1\n", set()),
    ("def test_x():\n    assert p._replace(a=1).a == 1\n", set()),
]


@pytest.mark.parametrize("src,expected", CASES, ids=[(c[1] and "+".join(sorted(c[1])) or "clean") + f"-{i}" for i, c in enumerate(CASES)])
def test_smells(tmp_path, src, expected):
    p = tmp_path / "test_s.py"
    p.write_text(src)
    assert {s["smell"] for s in smells.py_smells(str(p), ["pkg"])} == expected


def test_clones_cluster_copy_paste_tests_and_report_the_varying_literals(tmp_path):
    import json
    from types import SimpleNamespace
    src = "".join(f"def test_total_{i}():\n    assert total({i}, {-i}) == {i * 2}\n\n\n" for i in range(4))
    src += "def test_other():\n    assert other() is None\n"
    (tmp_path / "test_c.py").write_text(src)
    out = tmp_path / "c.json"
    smells.clones_main(SimpleNamespace(paths=[str(tmp_path)], out=str(out), min_size=3))
    rep = json.loads(out.read_text())
    assert rep["clusters"] == 1 and rep["items"][0]["size"] == 4
    assert rep["items"][0]["rows"][3] == ["3", "-3", "6"]      # negative literals fold into the row
