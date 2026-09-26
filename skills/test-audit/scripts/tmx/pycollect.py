"""Build a test matrix for a pytest project: per-test coverage, then a per-test kill matrix.

Runs entirely in throwaway copies of the project, so the working tree is never mutated.
The interpreter given by --python must have pytest and coverage installed.
"""
from __future__ import annotations

import concurrent.futures as cf
import difflib
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

from . import matrix as mx
from . import mutate_py

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE = shutil.ignore_patterns(".git", ".venv", "venv", "node_modules", "__pycache__", ".tox",
                                ".mypy_cache", ".pytest_cache", ".hypothesis", "*.pyc", ".coverage*")


def _run_pytest(python: str, cwd: str, out: str, cover: Optional[List[str]] = None,
                select: Optional[List[str]] = None, pytest_args: List[str] = (),
                timeout: Optional[float] = None) -> dict:
    env = dict(os.environ)
    # The copy's own tree first: an editable install of the original must not shadow the mutants.
    env["PYTHONPATH"] = os.pathsep.join([cwd, os.path.join(cwd, "src"), PLUGIN_DIR, env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMX_OUT"] = out
    env.pop("TMX_COVER", None)
    env.pop("TMX_SELECT", None)
    if cover:
        env["TMX_COVER"] = ",".join(cover)
    if select is not None:
        sel = out + ".select"
        with open(sel, "w") as f:
            f.write("\n".join(select) + "\n")
        env["TMX_SELECT"] = sel
    cmd = [python, "-m", "pytest", "-q", "-p", "tmx_pytest_plugin", "-p", "no:cacheprovider",
           "-p", "no:randomly", *pytest_args]
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    if not os.path.exists(out):
        return {"crashed": True, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:],
                "returncode": proc.returncode}
    with open(out) as f:
        res = json.load(f)
    os.remove(out)
    res["returncode"] = proc.returncode
    res["stdout_tail"] = proc.stdout[-2000:]
    return res


def _git_commit(root: str) -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def _py_files(root: str, sources: List[str]) -> List[str]:
    files = []
    for s in sources:
        p = os.path.join(root, s)
        if os.path.isfile(p) and p.endswith(".py"):
            files.append(os.path.relpath(p, root))
            continue
        for d, dirs, fs in os.walk(p):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x != "__pycache__"]
            for f in fs:
                if f.endswith(".py") and not f.startswith("test_") and not f.endswith("_test.py") \
                        and f != "conftest.py":
                    files.append(os.path.relpath(os.path.join(d, f), root))
    return sorted(files)


def collect(root: str, sources: List[str], tests: List[str], out_path: str, python: str = sys.executable,
            mutate: bool = True, jobs: int = 4, timeout_factor: float = 5.0, max_mutants: int = 0,
            operators: List[str] = mutate_py.OPERATORS, pytest_args: List[str] = (), log=print,
            per_line: int = 0, history: int = 0, extra: Optional[list] = None) -> dict:
    root = os.path.abspath(root)
    work = tempfile.mkdtemp(prefix="tmx-")
    try:
        base = os.path.join(work, "base")
        shutil.copytree(root, base, ignore=IGNORE, symlinks=True)
        log(f"[tmx] baseline run with per-test coverage ({python})")
        res = _run_pytest(python, base, os.path.join(work, "base.json"), cover=sources,
                          pytest_args=[*pytest_args, *tests])
        if res.get("crashed") or res.get("timeout"):
            raise SystemExit(f"baseline pytest run failed: {json.dumps(res)[:3000]}")
        failing = [t for t, r in res["tests"].items() if r.get("outcome") == "failed"]
        if failing:
            raise SystemExit(f"baseline has {len(failing)} failing tests (e.g. {failing[:3]}); "
                             "a kill matrix needs a green suite")
        m = {
            "schema": mx.SCHEMA, "root": root, "commit": _git_commit(root),
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "tool": {"collector": "pytest", "mutator": "tmx-python-ast" if mutate else None,
                     "operators": list(operators) if mutate else []},
            "scope": {"source": sources, "tests": tests},
            "tests": {t: r for t, r in res["tests"].items() if r.get("outcome") != "skipped"},
            "coverage": {t: c for t, c in res.get("coverage", {}).items() if t in res["tests"]},
            "mutants": {},
        }
        line_tests: Dict[str, List[str]] = {}
        for t, cov in m["coverage"].items():
            for ln in cov:
                line_tests.setdefault(ln, []).append(t)
        if not mutate:
            mx.save(m, out_path)
            return m

        src_lines = sum(1 for cov in m["coverage"].values() for ln in cov
                        if any(ln.startswith(x.rstrip("/")) for x in sources))
        if not src_lines:
            raise SystemExit("baseline coverage recorded no line of --src in the test run: the tests are not "
                             "importing this checkout's source (an installed copy shadows it?), so every mutant "
                             "would look harmless. Fix the import path before collecting a matrix.")
        m["tool"].update({"per_line": per_line, "history": history, "max_mutants": max_mutants})
        m["tool"]["extra"] = extra or []
        specs = build_specs(root, base, sources, operators, per_line, history, max_mutants, log, extra=extra)
        log(f"[tmx] {len(specs)} mutants over {len({s[0] for s in specs})} files; {jobs} workers")

        slots = []
        for j in range(jobs):
            d = os.path.join(work, f"w{j}")
            shutil.copytree(base, d, symlinks=True)
            slots.append(d)
        # Control: every worker must reproduce the green baseline unmutated. A harness that
        # cannot tell "mutant killed" from "harness broken" reports every mutant as killed.
        ctl = _run_pytest(python, slots[0], os.path.join(work, "control.json"), select=sorted(m["tests"]),
                          pytest_args=[*pytest_args, *tests])
        bad = [t for t, x in ctl.get("tests", {}).items() if x.get("outcome") == "failed"]
        if ctl.get("crashed") or ctl.get("timeout") or ctl.get("collection_errors") or bad or \
                len(ctl.get("tests", {})) != len(m["tests"]):
            raise SystemExit("control run (no mutation) is not green in a worker copy: "
                             f"{json.dumps({k: ctl.get(k) for k in ('crashed', 'collection_errors', 'errored_modules', 'stdout_tail')})[:2000]} "
                             f"failed={bad[:5]} ran={len(ctl.get('tests', {}))}/{len(m['tests'])}")
        free = list(slots)
        import threading
        lock = threading.Lock()

        all_tests = sorted(m["tests"])

        def run_one(i_spec):
            i, (rel, line, fam, desc, msrc, key) = i_spec
            mid = f"m{i:04d}"
            if fam == "history":  # a reverted fix may touch many lines: every test covering any of them
                covered = sorted({t for ln in desc["lines"] for t in line_tests.get(ln, [])})
                desc = desc["subject"]
            else:
                covered = sorted(set(line_tests.get(f"{rel}:{line}", [])))
            rec = {"file": rel, "line": line, "op": fam, "desc": desc, "key": key, "covered_by": covered,
                   "killed_by": []}
            with lock:
                d = free.pop()
            files = msrc if isinstance(msrc, dict) else {rel: msrc}
            origs = {}
            for frel in files:
                with open(os.path.join(d, frel)) as f:
                    origs[frel] = f.read()
            n_run = [0]

            def run(select):
                n_run[0] += 1
                budget = 10.0 + timeout_factor * sum(m["tests"][t].get("duration", 0.1) for t in select)
                return _run_pytest(python, d, os.path.join(work, f"{mid}-{n_run[0]}.json"), select=select,
                                   pytest_args=[*pytest_args, *tests], timeout=budget)

            def outcome(r, select):
                """(status, killers) for one run; None status means 'look further'."""
                if r.get("timeout"):
                    # Attribute exactly: each selected test alone; a hang or a failure is a kill.
                    killers = []
                    for t in select:
                        rr = run([t])
                        if rr.get("timeout") or any(x.get("outcome") == "failed" for x in rr.get("tests", {}).values()):
                            killers.append(t)
                    rec["note"] = "timeout; attributed by running the covering tests one at a time"
                    return ("killed" if killers else "timeout"), killers
                if r.get("crashed"):
                    rec["note"] = "pytest crashed under this mutant; not counted"
                    return "error", []
                killers = {t for t, x in r["tests"].items() if x.get("outcome") == "failed"}
                if r.get("collection_errors"):
                    errored = set(r.get("errored_modules", []))
                    killers |= {t for t in select if t.split("::")[0] in errored}
                    rec["note"] = "import/collection error in " + ", ".join(sorted(errored))[:200]
                    return ("killed" if killers else "error"), sorted(killers)
                return ("killed" if killers else None), sorted(killers)

            try:
                for frel, text in files.items():
                    with open(os.path.join(d, frel), "w") as f:
                        f.write(text)
                select = covered or all_tests
                status, killers = outcome(run(select), select)
                if status is None and select != all_tests:
                    # Survived its covering tests. Shared fixtures, caches and module state credit a
                    # line to one test only, so confirm survival against the whole suite before
                    # letting any reduction rely on it.
                    status, killers = outcome(run(all_tests), all_tests)
                    if status == "killed":
                        rec["note"] = "missed by its covering tests; the full suite kills it (shared state)"
                if status is None:
                    status = "survived" if covered else "no_coverage"
                if not covered and status != "no_coverage":
                    rec.setdefault("note", "no per-test coverage (import-time line?); ran the full suite")
            finally:
                for frel, text in origs.items():
                    with open(os.path.join(d, frel), "w") as f:
                        f.write(text)
                with lock:
                    free.append(d)
            rec["status"], rec["killed_by"] = status, killers
            return mid, rec

        done = 0
        with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
            for mid, rec in ex.map(run_one, enumerate(specs)):
                m["mutants"][mid] = rec
                done += 1
                if done % 25 == 0 or done == len(specs):
                    log(f"[tmx] {done}/{len(specs)} mutants")
        mx.save(m, out_path)
        return m
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_specs(root, base, sources, operators, per_line, history, max_mutants, log=print, extra=None) -> list:
    """Deterministic mutant list: (file, line, family, desc, mutated source(s), unique key)."""
    specs = []
    for rel in _py_files(base, sources):
        with open(os.path.join(base, rel)) as f:
            src = f.read()
        for line, fam, desc, msrc in mutate_py.mutants_for(src, operators):
            specs.append((rel, line, fam, desc, msrc))
    if per_line:
        # Google-style: at most `per_line` mutants per source line, chosen deterministically.
        by_line: Dict[tuple, list] = {}
        for sp in specs:
            by_line.setdefault((sp[0], sp[1]), []).append(sp)
        specs = []
        for k in sorted(by_line):
            specs.extend(sorted(by_line[k], key=lambda sp: (hash_str(sp[4]) % 997, sp[3]))[:per_line])
    for x in extra or []:
        # Domain faults the operators cannot express: {"file", "find", "replace", "desc"}; `find`
        # must occur exactly once in the current file, or the mutant is stale and is skipped.
        fp = os.path.join(base, x["file"])
        text = open(fp).read() if os.path.exists(fp) else ""
        if text.count(x["find"]) != 1:
            log(f"[tmx] extra mutant skipped (find text occurs {text.count(x['find'])}x): {x.get('desc', x['find'])[:60]}")
            continue
        line = text[:text.index(x["find"])].count("\n") + 1
        specs.append((x["file"], line, "extra", x.get("desc", x["replace"])[:120], text.replace(x["find"], x["replace"])))
    if history:
        hist = history_mutants(root, base, sources, history)
        log(f"[tmx] {len(hist)} history mutants (reverted past fixes that still apply)")
        specs.extend(hist)
    if max_mutants and len(specs) > max_mutants:
        step = len(specs) / max_mutants  # deterministic even sample across files
        specs = [specs[int(i * step)] for i in range(max_mutants)]
    seen: Dict[str, int] = {}
    out = []
    for rel, line, fam, desc, msrc in specs:
        d = desc["subject"] if isinstance(desc, dict) else desc
        k = f"{rel}:{line}:{fam}:{d}"
        seen[k] = seen.get(k, 0) + 1
        out.append((rel, line, fam, desc, msrc, f"{k}#{seen[k]}"))   # unique even for `0 <= x <= 10`
    return out


def hash_str(s: str) -> int:
    import zlib
    return zlib.crc32(s.encode())


def history_mutants(root: str, base: str, sources: List[str], n: int,
                    pattern: str = r"\b(fix|bug|regress|hotfix|patch|issue|crash|wrong|incorrect)") -> list:
    """Real-fault mutants: reverse-apply recent bug-fix commits to the current source.

    A reverted fix that still applies cleanly re-introduces a bug that really happened
    (Just et al. 2014: 17% of real faults couple to no classic mutant). Each becomes one mutant
    whose covering tests are those covering any line the revert touches.
    """
    import re
    try:
        log_out = subprocess.run(["git", "log", f"-n{n * 5}", "--format=%H%x09%s", "--", *sources], cwd=root,
                                 capture_output=True, text=True, check=True).stdout
    except Exception:
        return []
    out = []
    for row in log_out.splitlines():
        sha, _, subject = row.partition("\t")
        if not re.search(pattern, subject, re.I):
            continue
        diff = subprocess.run(["git", "diff", f"{sha}^", sha, "--", *sources], cwd=root,
                              capture_output=True, text=True).stdout
        if not diff.strip():
            continue
        scratch = tempfile.mkdtemp(prefix="tmx-hist-")
        try:
            files = sorted(set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.M)))
            if not files or not all(f.endswith(".py") and os.path.exists(os.path.join(base, f)) for f in files):
                continue
            for f in files:
                os.makedirs(os.path.dirname(os.path.join(scratch, f)) or scratch, exist_ok=True)
                shutil.copy(os.path.join(base, f), os.path.join(scratch, f))
            patch = os.path.join(scratch, "fix.diff")
            with open(patch, "w") as fh:
                fh.write(diff)
            r = subprocess.run(["git", "apply", "-R", "--unidiff-zero", patch], cwd=scratch, capture_output=True, text=True)
            if r.returncode != 0:
                continue  # the code has moved on; this fault no longer maps onto HEAD
            texts = {}
            for f in files:
                with open(os.path.join(scratch, f)) as fh:
                    texts[f] = fh.read()
            lines = []
            for f in files:  # lines of the CURRENT file that the revert changes (or deletes)
                with open(os.path.join(base, f)) as fh:
                    cur = fh.read().splitlines()
                sm = difflib.SequenceMatcher(a=cur, b=texts[f].splitlines(), autojunk=False)
                for tag, i1, i2, _, _ in sm.get_opcodes():
                    if tag != "equal":
                        lines += [f"{f}:{k + 1}" for k in range(i1, max(i2, i1 + 1))]
            out.append((files[0], int(lines[0].rsplit(":", 1)[1]) if lines else 1, "history",
                        {"subject": f"revert {sha[:8]}: {subject}"[:120], "lines": lines}, texts))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if len(out) >= n:
            break
    return out


def rerun_certificate(root: str, m: dict, plan: dict, python: str = sys.executable, jobs: int = 4,
                      pytest_args: List[str] = (), timeout_factor: float = 5.0, log=print) -> dict:
    """Empirical certificate check: replay every obligation's mutant against the RETAINED suite.

    The matrix is built from subset runs, so it can credit a kill to a test that only fails in
    that subset's order or context. This re-derives each mutant from its key and requires that
    the retained tests, run together exactly as they will run after the reduction, catch it. The
    retained suite must also be green on its own (order dependence shows up here first)."""
    root = os.path.abspath(root)
    tool = m.get("tool", {})
    sources, tests = m.get("scope", {}).get("source", []), m.get("scope", {}).get("tests", [])
    keep = list(plan["keep"])
    work = tempfile.mkdtemp(prefix="tmx-rerun-")
    try:
        base = os.path.join(work, "base")
        shutil.copytree(root, base, ignore=IGNORE, symlinks=True)
        specs = {sp[5]: sp for sp in build_specs(root, base, sources, tool.get("operators") or mutate_py.OPERATORS,
                                                  tool.get("per_line", 0), tool.get("history", 0),
                                                  tool.get("max_mutants", 0), log=lambda *_: None,
                                                  extra=tool.get("extra"))}
        wanted = []
        for ob in plan.get("certificate", {}):
            if not ob.startswith("mutant:"):
                continue
            mu = m["mutants"][ob[len("mutant:"):]]
            if mu.get("key") not in specs:
                return {"valid": False, "error": f"cannot regenerate {mu.get('key')}: source or matrix is stale"}
            wanted.append((ob, specs[mu["key"]]))
        ctl = _run_pytest(python, base, os.path.join(work, "ctl.json"), select=keep, pytest_args=[*pytest_args, *tests])
        bad = [t for t, x in ctl.get("tests", {}).items() if x.get("outcome") == "failed"]
        if ctl.get("crashed") or ctl.get("collection_errors") or bad or len(ctl.get("tests", {})) != len(keep):
            return {"valid": False, "error": "the retained suite is not green on its own (order dependence?)",
                    "failed": bad[:10], "ran": len(ctl.get("tests", {})), "expected": len(keep)}
        budget = 10.0 + timeout_factor * sum(m["tests"][t].get("duration", 0.1) for t in keep)
        slots = []
        for j in range(jobs):
            d = os.path.join(work, f"w{j}")
            shutil.copytree(base, d, symlinks=True)
            slots.append(d)
        import threading
        lock, free = threading.Lock(), list(slots)

        def one(item):
            ob, (rel, _l, _f, _d, msrc, _k) = item
            files = msrc if isinstance(msrc, dict) else {rel: msrc}
            with lock:
                d = free.pop()
            origs = {f: open(os.path.join(d, f)).read() for f in files}
            try:
                for f, text in files.items():
                    with open(os.path.join(d, f), "w") as fh:
                        fh.write(text)
                r = _run_pytest(python, d, os.path.join(work, ob.replace(":", "_") + ".json"), select=keep,
                                pytest_args=[*pytest_args, *tests], timeout=budget)
            finally:
                for f, text in origs.items():
                    with open(os.path.join(d, f), "w") as fh:
                        fh.write(text)
                with lock:
                    free.append(d)
            caught = r.get("timeout") or r.get("collection_errors") or \
                any(x.get("outcome") == "failed" for x in r.get("tests", {}).values())
            return ob, bool(caught)

        with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(one, wanted))
        missed = sorted(ob for ob, ok in results if not ok)
        return {"valid": not missed, "replayed": len(results), "missed": missed}
    finally:
        shutil.rmtree(work, ignore_errors=True)
