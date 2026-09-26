#!/usr/bin/env python3
"""Adopt the test constitution in a project: write TEST-CONSTITUTION.md, test-policy.toml, and
the managed testing block in CLAUDE.md and/or AGENTS.md. Idempotent for the managed block;
refuses to overwrite an existing constitution or policy unless --force.

  adopt.py --root . --src mypkg [--critical 'mypkg/billing/**' ...] [--max-tests N]
           [--max-seconds S] [--project NAME] [--agents CLAUDE.md,AGENTS.md] [--force] [--dry-run]

--max-tests defaults to the current test count (exact with --junit, else a static function count) (so adoption never fails CI on day one;
the audit then ratchets it down). Stdlib only.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
BEGIN, END = "<!-- test-skills:constitution:begin -->", "<!-- test-skills:constitution:end -->"


def count_tests(root: str, test_dirs=()) -> int:
    """Cheap static count (pytest-style and JS it/test). A real count comes from JUnit later.
    Counts only under --tests dirs when given (fixtures and vendored code are not the suite)."""
    n = 0
    tops = [os.path.join(root, t) for t in test_dirs] or [root]
    for d, dirs, fs in (w for top in tops for w in os.walk(top)):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in ("node_modules", "venv", "__pycache__", "fixtures")]
        for f in fs:
            p = os.path.join(d, f)
            if re.match(r"(test_.*|.*_test)\.py$", f):
                n += len(re.findall(r"^\s*(?:async\s+)?def test", open(p, errors="replace").read(), re.M))
            elif re.search(r"\.(test|spec)\.[jt]sx?$", f):
                n += len(re.findall(r"^\s*(?:it|test)(?:\.each\([^)]*\))?\s*\(", open(p, errors="replace").read(), re.M))
    return n


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def upsert_block(path: str, block: str, dry: bool) -> str:
    old = open(path).read() if os.path.exists(path) else ""
    if BEGIN in old and END in old:
        new = old[:old.index(BEGIN)] + block.strip() + old[old.index(END) + len(END):]
        action = "updated"
    else:
        new = old.rstrip() + ("\n\n" if old.strip() else "") + block.strip() + "\n"
        action = "appended"
    if new == old:
        return "unchanged"
    if not dry:
        with open(path, "w") as f:
            f.write(new)
    return action


def main(argv) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--src", required=True, help="main source root, e.g. src/mypkg")
    p.add_argument("--critical", action="append", default=[], help="glob of critical-tier code (repeatable)")
    p.add_argument("--rigor", default="R3", help="project default rigor profile R1..R5")
    p.add_argument("--critical-rigor", default="R4", help="rigor profile for the critical tier")
    p.add_argument("--tests", action="append", default=[], help="test roots to count (default: whole repo minus fixtures)")
    p.add_argument("--junit", help="JUnit XML of a full run: exact case count for the day-one budget (preferred)")
    p.add_argument("--max-tests", type=int)
    p.add_argument("--max-seconds", type=int, default=300)
    p.add_argument("--max-new", type=int, default=8)
    p.add_argument("--project")
    p.add_argument("--agents", default="CLAUDE.md", help="comma list of agent-instruction files to update")
    p.add_argument("--codeowners", help="owner (e.g. @org/test-owners) for the governance files in .github/CODEOWNERS")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    root = os.path.abspath(a.root)
    n = count_tests(root, a.tests)
    if a.junit:  # parametrized rows are separate cases; only a real run counts them
        import xml.etree.ElementTree as ET
        n = sum(1 for _ in ET.parse(a.junit).getroot().iter("testcase"))
    # Today's count plus one change's worth: a zero-headroom budget blocks even a good test for a real
    # gap until the suite has been reduced (seen in evaluation). The ratchet brings it down afterwards.
    max_tests = a.max_tests if a.max_tests is not None else max(20, n + a.max_new)
    src = a.src.rstrip("/")
    values = {
        "project": a.project or os.path.basename(root),
        "date": dt.date.today().isoformat(),
        "src": src,
        "max_tests": max_tests,
        "max_seconds": a.max_seconds,
        "max_new": a.max_new,
        "rigor": a.rigor.upper(),
        "critical_rigor": max(a.critical_rigor.upper(), a.rigor.upper()),
        "critical_paths": json.dumps(a.critical or [f"{src}/**/billing*", f"{src}/**/auth*"]),
    }
    report = {"tests_found": n, "max_tests": max_tests, "written": {}}
    for name in ("TEST-CONSTITUTION.md", "test-policy.toml"):
        dst = os.path.join(root, name)
        if os.path.exists(dst) and not a.force:
            report["written"][name] = "exists (kept; use --force to overwrite)"
            continue
        text = fill(open(os.path.join(ASSETS, name)).read(), values)
        if not a.dry_run:
            with open(dst, "w") as f:
                f.write(text)
        report["written"][name] = "written"
    if a.max_new != 8:
        pol = os.path.join(root, "test-policy.toml")
        if os.path.exists(pol) and not a.dry_run:
            t = open(pol).read()
            open(pol, "w").write(re.sub(r"max_new_tests_per_pr = \d+", f"max_new_tests_per_pr = {a.max_new}", t))
    block = fill(open(os.path.join(ASSETS, "agent-block.md")).read(), values)
    for fname in [x.strip() for x in a.agents.split(",") if x.strip()]:
        report["written"][fname] = upsert_block(os.path.join(root, fname), block, a.dry_run)
    prot = os.path.join(root, "testing", "protected.txt")
    if not os.path.exists(prot) and not a.dry_run:
        os.makedirs(os.path.dirname(prot), exist_ok=True)
        with open(prot, "w") as f:
            f.write("# Exact test ids exempt from the unique-kill admission rule (regressions for real bugs).\n"
                    "# Read from the base branch by the gate: adding an id takes its own reviewed change.\n")
        report["written"]["testing/protected.txt"] = "written"
    if a.codeowners and not a.dry_run:
        co = os.path.join(root, ".github", "CODEOWNERS")
        os.makedirs(os.path.dirname(co), exist_ok=True)
        cur = open(co).read() if os.path.exists(co) else ""
        lines = [f"/{n} {a.codeowners}" for n in ("TEST-CONSTITUTION.md", "test-policy.toml", ".test-baseline.json",
                                                  ".test-probation.json", ".test-quarantine.json", "testing/protected.txt",
                                                  "testing/survivors.json")]
        add = [ln for ln in lines if ln not in cur]
        if add:
            with open(co, "a") as f:
                f.write(("\n" if cur and not cur.endswith("\n") else "") + "# test governance (test-skills)\n" + "\n".join(add) + "\n")
            report["written"][".github/CODEOWNERS"] = f"{len(add)} governance entries"
    gi = os.path.join(root, ".gitignore")
    if not a.dry_run:
        cur = open(gi).read() if os.path.exists(gi) else ""
        if ".tmx/" not in cur.split():
            with open(gi, "a") as f:
                f.write(("\n" if cur and not cur.endswith("\n") else "") + ".tmx/\n")
            report["written"][".gitignore"] = "added .tmx/"
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
