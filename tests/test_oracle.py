"""The differential oracle's own proof (TS-11, DEC-189).

Each clause of the ruling gets a case: identical observable results are
equivalent; a difference in return value, exit code, emitted record or file
written is not; and a difference in wall time or iteration count alone is.
"""
import sys

from tmx import oracle


def tree(tmp_path, name, src):
    d = tmp_path / name
    d.mkdir()
    (d / "prog.py").write_text(src)
    return str(d)


def verdict(tmp_path, base, mutant, corpus=(("prog.py",),)):
    o = tree(tmp_path, "orig", base)
    m = tree(tmp_path, "mut", mutant)
    return oracle.equivalent(sys.executable, o, m, [list(c) for c in corpus], seed=7)


def test_identical_observable_results_are_equivalent(tmp_path):
    res = verdict(tmp_path, "print('hi')\n", "print('hi')\n")
    assert res["equivalent"] is True and res["seed"] == 7
    assert all(e["same"] for e in res["evidence"])


def test_a_different_return_value_is_not_equivalent(tmp_path):
    res = verdict(tmp_path, "print(1 + 1)\n", "print(1 - 1)\n")
    assert res["equivalent"] is False
    assert res["evidence"][-1]["original"]["stdout"] != res["evidence"][-1]["mutant"]["stdout"]


def test_a_different_exit_code_is_not_equivalent(tmp_path):
    res = verdict(tmp_path, "pass\n", "import sys\nsys.exit(3)\n")
    assert res["equivalent"] is False
    assert res["evidence"][-1]["mutant"]["exit"] == 3


def test_a_file_written_by_only_one_side_is_not_equivalent(tmp_path):
    res = verdict(tmp_path, "pass\n", "open('out.txt', 'w').write('x')\n")
    assert res["equivalent"] is False
    assert res["evidence"][-1]["mutant"]["written"] == ["out.txt"]


def test_a_difference_in_iteration_count_alone_is_equivalent(tmp_path):
    base = "x = 0\nfor _ in range(3):\n    x = 1\nprint(x)\n"
    mutant = "x = 0\nfor _ in range(300000):\n    x = 1\nprint(x)\n"
    assert verdict(tmp_path, base, mutant)["equivalent"] is True


def test_a_difference_in_wall_time_alone_is_equivalent(tmp_path):
    base = "print('done')\n"
    mutant = "import time\ntime.sleep(0.3)\nprint('done')\n"
    assert verdict(tmp_path, base, mutant)["equivalent"] is True


def test_evidence_stops_at_the_first_mismatch(tmp_path):
    # Two entries; the first already differs, so the second is not run.
    res = verdict(tmp_path, "print('a')\n", "print('b')\n",
                  corpus=(("prog.py",), ("prog.py",)))
    assert res["equivalent"] is False and len(res["evidence"]) == 1
