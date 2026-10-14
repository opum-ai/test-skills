"""The differential oracle's own proof (TS-11, DEC-189).

Each clause of the ruling gets a case: identical observable results are
equivalent; a difference in return value, exit code, emitted record or file
written is not; and a difference in wall time or iteration count alone is.
"""
import os
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


# --- review fixes (test-skills#14, DEC-189) ---------------------------------


def test_an_unexecuted_line_is_unreached_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "print('hi')\n")
    m = tree(tmp_path, "mut", "print('hi')\n")
    res = oracle.equivalent(sys.executable, o, m, [["prog.py"]], seed=7,
                            required_lines=[2], covered=[1])
    assert res["equivalent"] is False and res["unreached"] is True and res["missing_lines"] == [2]


def test_a_reached_line_with_a_matching_result_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "print('hi')\n")
    m = tree(tmp_path, "mut", "print('hi')\n")
    res = oracle.equivalent(sys.executable, o, m, [["prog.py"]], seed=7,
                            required_lines=[1], covered=[1, 2])
    assert res["equivalent"] is True and res["unreached"] is False


def test_a_write_to_the_sandboxed_home_is_observable(tmp_path):
    mutant = "import os\nopen(os.path.join(os.path.expanduser('~'), 'x'), 'w').write('1')\n"
    assert verdict(tmp_path, "pass\n", mutant)["equivalent"] is False


def test_a_write_to_an_absolute_path_outside_the_tree_is_not_seen(tmp_path):
    # Documents the stated limitation: a write outside the watched tree is invisible.
    out = tmp_path / "outside.txt"
    mutant = f"open({str(out)!r}, 'w').write('x')\n"
    assert verdict(tmp_path, "pass\n", mutant)["equivalent"] is True


def test_a_stderr_only_difference_is_not_equivalent(tmp_path):
    assert verdict(tmp_path, "pass\n", "import sys\nsys.stderr.write('boom')\n")["equivalent"] is False


def test_the_same_stderr_from_a_different_source_is_equivalent(tmp_path):
    base = "import sys\nsys.stderr.write('same')\n"
    mutant = "import sys  # a different source\nsys.stderr.write('same')\n"
    assert verdict(tmp_path, base, mutant)["equivalent"] is True


def test_a_file_changed_to_different_content_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "open('f.txt', 'w').write('a')\n")
    m = tree(tmp_path, "mut", "open('f.txt', 'w').write('b')\n")
    assert oracle.equivalent(sys.executable, o, m, [["prog.py"]])["equivalent"] is False


def test_the_same_file_written_by_both_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "open('f.txt', 'w').write('a')\n")
    m = tree(tmp_path, "mut", "open('f.txt', 'w').write('a')\n")
    assert oracle.equivalent(sys.executable, o, m, [["prog.py"]])["equivalent"] is True


def test_a_removed_file_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "import os\nos.remove('seed.txt')\n")
    for d in (o, m):
        open(os.path.join(d, "seed.txt"), "w").write("x")
    assert oracle.equivalent(sys.executable, o, m, [["prog.py"]])["equivalent"] is False


def test_a_present_unchanged_file_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "pass\n")
    for d in (o, m):
        open(os.path.join(d, "seed.txt"), "w").write("x")
    assert oracle.equivalent(sys.executable, o, m, [["prog.py"]])["equivalent"] is True


def test_a_file_mode_change_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "import os\nos.chmod('seed.txt', 0o600)\n")
    for d in (o, m):
        p = os.path.join(d, "seed.txt")
        open(p, "w").write("x")
        os.chmod(p, 0o644)
    assert oracle.equivalent(sys.executable, o, m, [["prog.py"]])["equivalent"] is False
