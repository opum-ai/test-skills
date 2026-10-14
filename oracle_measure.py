"""Measure E: how many critical-tier survivors are provably equivalent (TS-11, DEC-189).

A tooling run, not a test, so it costs no Art. II slots. For each survivor it
loads the mutant's source in a subprocess (so a mutant that disables the
solver's own time budget cannot hang the driver), runs a fixed seeded generated
corpus, and compares the observable result to the original's. It also reports
the corpus's line coverage of each module, so an un-exercised mutant cannot read
as equivalent.

  python oracle_measure.py --matrix .tmx/crit.json     # measure E + coverage
  python oracle_measure.py --worker <src> <module>     # (internal subprocess)
"""
import argparse
import hashlib
import importlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = None  # set below once SCRIPTS is known
_CANDS = [HERE, os.path.dirname(HERE), "/Volumes/external/repos/test-skills"]
SCRIPTS = next((os.path.join(r, "skills", "test-audit", "scripts") for r in _CANDS
                if os.path.isdir(os.path.join(r, "skills", "test-audit", "scripts"))),
               os.path.join(HERE, "skills", "test-audit", "scripts"))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPTS)))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
SEED = 20261014
MODULES = ["cover.py", "gate.py", "rigor.py", "matrix.py"]


def corpus(g, module, rnd):
    """Run a fixed seeded corpus against a loaded module; return the observable result list."""
    out = []
    if module == "cover.py":
        I, S, C = g["Instance"], g["solve"], g["certificate"]
        CC, CR, CV, PC = g["check_certificate"], g["classify_removed"], g["curve"], g["popcount"]
        for _ in range(200):
            nt, no = rnd.randint(1, 10), rnd.randint(1, 14)
            tests = {f"t{i}": {f"o{j}" for j in range(no) if rnd.random() < 0.5} for i in range(nt)}
            objs = sorted({o for s in tests.values() for o in s})
            if not objs:
                continue
            inst = I(objs, tests, {t: 1.0 for t in tests})
            r = S(inst, node_budget=10000, time_budget_s=0.15)
            keep = r["keep"]
            w, miss = C(inst, keep)
            killers = {o: {t for t, s in tests.items() if o in s} for o in objs}
            out.append((tuple(keep), r["cost"], r["optimal"], tuple((a, b) for a, b, _ in CV(inst)),
                        tuple(miss), tuple(CC(killers, set(keep), w)),
                        json.dumps(CR(inst, keep), sort_keys=True), PC(inst.full)))
    elif module == "matrix.py":
        MS, OB, PT = g["mutation_score"], g["obligations"], g["per_test"]
        for _ in range(200):
            n = rnd.randint(0, 6)
            ms = {f"m{i}": {"status": rnd.choice(["killed", "survived", "no_coverage", "timeout", "error"]),
                            "killed_by": [f"t{rnd.randint(0, 3)}"]} for i in range(n)}
            m = {"tests": {f"t{i}": {} for i in range(4)}, "mutants": ms,
                 "coverage": {f"t{i}": [f"f:{i}", f"f:{i + 1}"] for i in range(4)}}
            tests = {f"t{i}" for i in range(4)}
            out.append((MS(m, tests=tests), json.dumps(OB(m, lines=True), sort_keys=True, default=str),
                        json.dumps({k: sorted(v) for k, v in PT(OB(m), tests).items()}, sort_keys=True)))
    elif module == "rigor.py":
        H, R = g["highest"], g["rules"]
        pick_names = ["R1", "R2", "R3", "R4", "R5"]
        for _ in range(200):
            pick = [rnd.choice(pick_names) for _ in range(rnd.randint(1, 4))]
            out.append((H(pick), json.dumps(R(rnd.choice(pick_names), {}), sort_keys=True, default=str)))
    elif module == "gate.py":
        MT, MATCH, TIER, APPR = g["mini_toml"], g["_match"], g["_tier_of"], g["_approvers"]
        SPLIT, LLT = g["_split_top"], g["_load_list_text"]
        for _ in range(150):
            txt = 'version = %d\nrigor = "R%d"\n[budget]\nmax_tests = %d\n[[adequacy.tier]]\nname = "t"\npaths = ["%s"]\n' % (
                rnd.randint(1, 2), rnd.randint(1, 5), rnd.randint(1, 99), rnd.choice(["*.py", "pkg/*", "**/*.py"]))
            try:
                out.append(json.dumps(MT(txt), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
            out.append(tuple(SPLIT(rnd.choice(['a, b', '[1, 2]', '"x, y"', 'a,b,c']))))
            try:
                out.append(json.dumps(LLT(rnd.choice(['[]', '[{"t": 1}]', 'not json', '[1, 2]'])), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        for _ in range(80):
            p = rnd.choice(["a.py", "pkg/x.py", "tests/t.py", "deep/a/b.py"])
            out.append(MATCH(p, [rnd.choice(["*.py", "**", "pkg/*", "tests/*", "**/*.py"])]))
            out.append(json.dumps(TIER(p, [{"name": "c", "paths": ["pkg/*"]}, {"name": "s", "paths": ["*.py"]}]),
                                  sort_keys=True, default=str))
            out.append(json.dumps(sorted(APPR({"assurance": {"approvers": ["a", "b"]}}) or [])))
        d = "/tmp/tmx_oracle_light"
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d + "/tests")
        open(d + "/tests/test_a.py", "w").write("def test_a():\n    assert 1 + 1 == 2\n")
        pol = MT('version = 1\nrigor = "R3"\n[budget]\nmax_tests = 50\n[[adequacy.tier]]\nname = "c"\npaths = ["pkg/*"]\n')
        for _ in range(20):
            try:
                out.append(json.dumps(g["run"](pol, root=d, matrix_path=None), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        # Deeper: a real git repo with a base ref, a junit and a matrix, so run(), main() and
        # write_baseline are exercised (not just the parsers).
        import subprocess as _sp
        repo = "/tmp/tmx_oracle_gate_repo"
        shutil.rmtree(repo, ignore_errors=True)
        os.makedirs(repo + "/tests")
        open(repo + "/tests/test_a.py", "w").write("def test_a():\n    assert 1 + 1 == 2\n")

        def _g(*args):
            _sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo,
                    check=True, capture_output=True,
                    env=dict(os.environ, GIT_AUTHOR_DATE="2020-01-01T00:00:00+00:00",
                             GIT_COMMITTER_DATE="2020-01-01T00:00:00+00:00"))
        try:
            _g("init", "-q", "-b", "main"); _g("add", "-A"); _g("commit", "-qm", "init")
            _g("checkout", "-qb", "pr")
            open(repo + "/tests/test_a.py", "a").write("def test_b():\n    assert 2 + 2 == 4\n")
            _g("commit", "-qam", "add")
        except Exception as e:
            out.append("E:git:" + type(e).__name__)
        jf = repo + "/r.xml"
        open(jf, "w").write("<testsuite>" + "".join(
            f"<testcase classname='t' name='n{i}'/>" for i in range(3)) + "</testsuite>")
        mf = repo + "/m.json"
        json.dump({"schema": "test-matrix/1", "tests": {"a::t": {"duration": 0.1}},
                   "coverage": {"a::t": ["pkg/x.py:1"]},
                   "mutants": {"m1": {"file": "pkg/x.py", "line": 1, "op": "const", "desc": "1 -> 0",
                                      "status": "killed", "killed_by": ["a::t"]}}}, open(mf, "w"))
        deep = 'version = 1\nrigor = "%s"\n[budget]\nmax_tests = 50\nmax_new_tests_per_pr = 1\n' \
               '[[adequacy.tier]]\nname = "critical"\npaths = ["pkg/*"]\n[assurance]\napprovers = ["alice"]\n'
        for lvl in ["R1", "R3", "R4", "R5"]:
            p = MT(deep % lvl)
            for kw in (dict(root=repo, base="main"), dict(root=repo, base="main", junit=[jf]),
                       dict(root=repo, base="main", matrix_path=mf),
                       dict(root=repo, base="main", junit=[jf], matrix_path=mf,
                            pr_body="Test-Budget: reason\nRigor: R4\n")):
                try:
                    out.append(json.dumps(g["run"](p, **kw), sort_keys=True, default=str))
                except Exception as e:
                    out.append("E:" + type(e).__name__)
        open(repo + "/test-policy.toml", "w").write(deep % "R3")
        for ps, base in ((None, None), (None, "main"), ("base", "main")):
            a = argparse.Namespace(policy=repo + "/test-policy.toml", policy_source=ps, base=base,
                                   root=repo, junit=[jf], matrix=mf, json=True)
            try:
                out.append(g["main"](a))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        for kw in (dict(junit=[jf]), dict(matrix_path=mf), dict(junit=[jf], matrix_path=mf)):
            try:
                out.append(json.dumps(g["write_baseline"](repo, "bl.json", **kw), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        out.append(json.dumps(g["_load_list"](repo + "/nope.json"), default=str))
        # junit with failures and skips, a slow suite, a changed smell test, quarantine and triage.
        jf2 = repo + "/r2.xml"
        open(jf2, "w").write("<testsuite time='120.0'>" + "".join(
            f"<testcase classname='t' name='k{i}' time='1'>"
            f"{'<failure/>' if i % 3 == 0 else '<skipped/>' if i % 3 == 1 else ''}</testcase>"
            for i in range(30)) + "</testsuite>")
        mf2 = repo + "/m2.json"
        json.dump({"schema": "test-matrix/1", "tests": {"t::a": {}}, "coverage": {},
                   "mutants": {f"m{i}": {"file": "tests/test_a.py", "line": i + 1, "op": "const",
                                         "desc": "1 -> 0", "status": "survived", "killed_by": []}
                               for i in range(4)}}, open(mf2, "w"))
        os.makedirs(repo + "/testing", exist_ok=True)
        json.dump({"tests/test_a.py:1:const:1 -> 0": {"verdict": "equivalent", "reason": "r"}},
                  open(repo + "/testing/survivors.json", "w"))
        json.dump([{"test": "t::q", "issue": "", "owner": ""}], open(repo + "/.test-quarantine.json", "w"))
        json.dump({"tests": 3, "hidden_tests": 0, "test_ids": ["t::a"]}, open(repo + "/bl2.json", "w"))
        open(repo + "/tests/test_smell.py", "w").write("def test_smell():\n    run()\n")
        try:
            _g("add", "-A"); _g("commit", "-qm", "more")
        except Exception as e:
            out.append("E:git2:" + type(e).__name__)
        pol2 = MT(deep % "R4")
        for kw in (dict(root=repo, base="main", junit=[jf2]),
                   dict(root=repo, base="main", junit=[jf2], matrix_path=mf2),
                   dict(root=repo, base="main", matrix_path=mf2),
                   dict(root=repo, base="no-such-ref", junit=[jf2])):
            try:
                out.append(json.dumps(g["run"](pol2, **kw), sort_keys=True, default=str))
            except SystemExit as e:
                out.append("SX:" + str(e)[:40])
            except Exception as e:
                out.append("E:" + type(e).__name__)
        for lvl in ["R4", "R5"]:
            for v in [None, "bob", "alice"]:
                if v is None:
                    os.environ.pop("TMX_PR_APPROVERS", None)
                else:
                    os.environ["TMX_PR_APPROVERS"] = v
                try:
                    out.append(json.dumps(g["run"](MT(deep % lvl), root=repo, base="main", junit=[jf2]),
                                          sort_keys=True, default=str))
                except Exception as e:
                    out.append("E:" + type(e).__name__)
        os.environ.pop("TMX_PR_APPROVERS", None)
        for js in (True, False):
            np = argparse.Namespace(policy=repo + "/test-policy.toml", policy_source=None, base="main",
                                    root=repo, junit=[jf2], matrix=mf2, json=js)
            try:
                out.append(g["main"](np))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        missing_pol = argparse.Namespace(policy=repo + "/nope.toml", policy_source=None, base=None,
                                         root=repo, junit=[jf2], matrix=mf2, json=False)
        try:
            out.append(g["main"](missing_pol))
        except Exception as e:
            out.append("E:" + type(e).__name__)
        # Triers: a tier whose path matches the changed survivor file (so the triage block runs),
        # and a budget the junit busts.
        deep_tests = deep.replace('paths = ["pkg/*"]', 'paths = ["tests/*"]')
        pol3 = MT(deep_tests % "R4")
        for kw in (dict(root=repo, base="main", matrix_path=mf2),
                   dict(root=repo, base="main", matrix_path=mf2, junit=[jf2])):
            try:
                out.append(json.dumps(g["run"](pol3, **kw), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        pol4 = MT((deep_tests.replace("max_tests = 50", "max_tests = 1")
                   .replace("max_new_tests_per_pr = 1", "max_new_tests_per_pr = 0")) % "R5")
        for kw in (dict(root=repo, base="main", junit=[jf2], matrix_path=mf2),
                   dict(root=repo, base="main", junit=[jf2])):
            try:
                out.append(json.dumps(g["run"](pol4, **kw), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        # main() judging by the base policy (both branches) and the text report path.
        for ps in ("base", "head"):
            a2 = argparse.Namespace(policy=repo + "/test-policy.toml", policy_source=ps, base="main",
                                    root=repo, junit=[jf2], matrix=mf2, json=False)
            try:
                out.append(g["main"](a2))
            except Exception as e:
                out.append("E:" + type(e).__name__)
        # run() with a baseline carrying test ids (moves growth and unique-kill paths).
        pol5 = dict(MT(deep_tests % "R4"))
        pol5["_baseline_text"] = json.dumps({"tests": 1, "hidden_tests": 0, "test_ids": ["t::a"]})
        for kw in (dict(root=repo, matrix_path=mf2, junit=[jf2]), dict(root=repo, matrix_path=mf2)):
            try:
                out.append(json.dumps(g["run"](pol5, **kw), sort_keys=True, default=str))
            except Exception as e:
                out.append("E:" + type(e).__name__)
    return out


def _load(name, source):
    import importlib.util
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__package__ = "tmx"
    exec(compile(source, name, "exec"), m.__dict__)
    return m


def worker(path, module):
    g = _load("tmx._mut_" + module.replace(".", "_"), open(path).read()).__dict__
    print(hashlib.sha256(repr(corpus(g, module, random.Random(SEED))).encode()).hexdigest())


def coverage_of(module):
    import coverage
    path = os.path.join(SCRIPTS, "tmx", module)
    sys.modules.pop("tmx." + module[:-3], None)
    cov = coverage.Coverage(include=[path], data_file=None)
    cov.start()
    m = importlib.import_module("tmx." + module[:-3])
    corpus(m.__dict__, module, random.Random(SEED))
    cov.stop()
    _fn, statements, _excl, missing, _mf = cov.analysis2(path)
    return set(statements) - set(missing), len(statements)


def survivor_specs(matrix_path, module):
    from tmx import mutate_py
    m = json.load(open(matrix_path))
    want = {(mu["line"], mu["op"], mu.get("desc")) for k, mu in m["mutants"].items()
            if mu.get("file", "").split("/")[-1] == module and mu["status"] in ("survived", "no_coverage")}
    src = open(os.path.join(SCRIPTS, "tmx", module)).read()
    specs = [(line, fam, desc, msrc) for (line, fam, desc, msrc) in mutate_py.mutants_for(src)
             if (line, fam, desc) in want]
    return src, specs


def measure(matrix_path, modules=MODULES):
    artifact = {"seed": SEED, "matrix": matrix_path, "modules": {}}
    total_eq = 0

    def run(src, module):
        f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
        f.write(src); f.close()
        try:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", f.name, module],
                               capture_output=True, text=True, timeout=12)
            return r.stdout.strip() or ("ERR:" + r.stderr.strip()[-160:])
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        finally:
            os.unlink(f.name)

    for module in modules:
        src, specs = survivor_specs(matrix_path, module)
        base = run(src, module)
        covered, cov_total = coverage_of(module)
        eq = 0; unreached_eq = 0
        ev = []
        for line, fam, desc, msrc in specs:
            h = run(msrc, module)
            same = h == base and h not in ("", "TIMEOUT") and not h.startswith("ERR:")
            reached = line in covered
            # DEC-189: equivalent only if the corpus EXECUTES the mutated line.
            if same and reached:
                eq += 1
            elif same:
                unreached_eq += 1
            ev.append({"line": line, "op": fam, "desc": desc, "equivalent": same and reached,
                       "same_result": same, "reached": reached})
        total_eq += eq
        pct = round(100.0 * len(covered) / cov_total, 1) if cov_total else None
        artifact["modules"][module] = {"survivors": len(specs), "equivalent": eq,
                                       "equivalent_unreached": unreached_eq,
                                       "observable": len(specs) - eq - unreached_eq,
                                       "coverage_pct": pct, "coverage": f"{len(covered)}/{cov_total}", "evidence": ev}
        print(f"{module}: {len(specs)} survivors, {eq} eq(reached), {unreached_eq} eq(unreached), "
              f"{len(specs)-eq-unreached_eq} obs; corpus covers {len(covered)}/{cov_total} lines ({pct}%)")
    artifact["equivalent_total"] = total_eq
    outp = os.path.join(REPO, ".tmx", "oracle-e.json")
    json.dump(artifact, open(outp, "w"), indent=1)
    print(f"TOTAL equivalent: {total_eq}; artifact -> {outp}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", nargs=2, metavar=("SRC", "MODULE"))
    ap.add_argument("--matrix", default=os.path.join(REPO, ".tmx", "crit.json"))
    a = ap.parse_args()
    if a.worker:
        worker(a.worker[0], a.worker[1])
    else:
        measure(a.matrix)
