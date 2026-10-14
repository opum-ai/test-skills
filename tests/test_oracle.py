"""The differential oracle's own proof (TS-11, DEC-189).

Each clause of the ruling gets a case: identical observable results are
equivalent; a difference in return value, exit code, emitted record or file
written is not; a difference in wall time or iteration count alone is; and the
reach guard fails closed. Review findings from test-skills#14 are pinned by
declaring reach on every call and, in the stderr case, by having the programs
import a sibling module and leave a tempfile (so a compiled sibling and a
random-named temp file cannot make an equivalent mutant read as observable).
"""
import os
import sys

from tmx import oracle

REACH = list(range(1, 60))


def tree(tmp_path, name, src):
    d = tmp_path / name
    d.mkdir()
    (d / "prog.py").write_text(src)
    return str(d)


def equiv(o, m, corpus=(("prog.py",),), **kw):
    kw.setdefault("required_lines", [1])
    kw.setdefault("covered", REACH)
    return oracle.equivalent(sys.executable, o, m, [list(c) for c in corpus], seed=7, **kw)


def verdict(tmp_path, base, mutant, corpus=(("prog.py",),)):
    return equiv(tree(tmp_path, "orig", base), tree(tmp_path, "mut", mutant), corpus)


def test_identical_observable_results_are_equivalent(tmp_path):
    # The program prints its absolute working directory, which differs per tree; normalisation
    # must remove it, and the recorded environment must carry no absolute path.
    res = verdict(tmp_path, "import os\nprint(os.getcwd())\n", "import os\nprint(os.getcwd())\n")
    assert res["equivalent"] is True and res["seed"] == 7 and res["observed"] == "workspace, home, tmp"
    assert all(e["same"] for e in res["evidence"])
    mut = res["evidence"][-1]["mutant"]
    assert "<RUN>" in mut["stdout"] and str(tmp_path) not in mut["stdout"]
    assert mut["env"]["PYTHONHASHSEED"] == "0" and not any(str(tmp_path) in v for v in mut["env"].values())


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
    res = equiv(o, m, required_lines=[2], covered=[1])
    assert res["equivalent"] is False and res["unreached"] is True and res["missing_lines"] == [2]
    # The reach guard FAILS CLOSED: no reach information at all is unreached, not equivalent.
    none = oracle.equivalent(sys.executable, o, m, [["prog.py"]], seed=7)
    assert none["equivalent"] is False and none["unreached"] is True
    assert none["reason"] == "no reach information"


def test_a_reached_line_with_a_matching_result_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "print('hi')\n")
    m = tree(tmp_path, "mut", "print('hi')\n")
    res = equiv(o, m, required_lines=[1], covered=[1, 2])
    assert res["equivalent"] is True and res["unreached"] is False


def test_a_write_to_the_sandboxed_home_is_observable(tmp_path):
    mutant = "import os\nopen(os.path.join(os.path.expanduser('~'), 'x'), 'w').write('1')\n"
    assert verdict(tmp_path, "pass\n", mutant)["equivalent"] is False


def test_a_write_outside_the_sandbox_is_a_known_false_equivalent(tmp_path):
    # DEC-189 (5): the documented BOUNDARY of a process-level oracle, not a claim that a mutant
    # writing to an absolute path outside the workspace is truly equivalent. The verdict records
    # the channels observed; this case asserts the limitation so it stays visible.
    out = tmp_path / "outside.txt"
    mutant = f"open({str(out)!r}, 'w').write('x')\n"
    res = verdict(tmp_path, "pass\n", mutant)
    assert res["equivalent"] is True and res["observed"] == "workspace, home, tmp"


def test_a_stderr_only_difference_is_not_equivalent(tmp_path):
    assert verdict(tmp_path, "pass\n", "import sys\nsys.stderr.write('boom')\n")["equivalent"] is False


def test_the_same_stderr_from_a_different_source_is_equivalent(tmp_path):
    # Both import a sibling module (which would leave a __pycache__/*.pyc) and leave a
    # random-named tempfile. Neither may make the mutant observable.
    prog = "import sys, tempfile, mod\ntempfile.mkstemp()\nsys.stderr.write('same')\n"
    o = tree(tmp_path, "orig", prog)
    m = tree(tmp_path, "mut", prog + "# a different source\n")
    for d in (o, m):
        open(os.path.join(d, "mod.py"), "w").write("X = 1\n")
    assert equiv(o, m)["equivalent"] is True


def test_a_file_changed_to_different_content_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "open('f.txt', 'w').write('a')\n")
    m = tree(tmp_path, "mut", "open('f.txt', 'w').write('b')\n")
    assert equiv(o, m)["equivalent"] is False


def test_the_same_file_written_by_both_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "open('f.txt', 'w').write('a')\n")
    m = tree(tmp_path, "mut", "open('f.txt', 'w').write('a')\n")
    assert equiv(o, m)["equivalent"] is True


def test_a_removed_file_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "import os\nos.remove('seed.txt')\n")
    for d in (o, m):
        open(os.path.join(d, "seed.txt"), "w").write("x")
    assert equiv(o, m)["equivalent"] is False


def test_a_present_unchanged_file_is_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "pass\n")
    for d in (o, m):
        open(os.path.join(d, "seed.txt"), "w").write("x")
    assert equiv(o, m)["equivalent"] is True


def test_a_file_mode_change_is_not_equivalent(tmp_path):
    o = tree(tmp_path, "orig", "pass\n")
    m = tree(tmp_path, "mut", "import os\nos.chmod('seed.txt', 0o600)\n")
    for d in (o, m):
        p = os.path.join(d, "seed.txt")
        open(p, "w").write("x")
        os.chmod(p, 0o644)
    assert equiv(o, m)["equivalent"] is False
