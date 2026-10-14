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
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "skills", "test-audit", "scripts")
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
        d = tempfile.mkdtemp()
        os.makedirs(d + "/tests")
        open(d + "/tests/test_a.py", "w").write("def test_a():\n    assert 1 + 1 == 2\n")
        pol = MT('version = 1\nrigor = "R3"\n[budget]\nmax_tests = 50\n[[adequacy.tier]]\nname = "c"\npaths = ["pkg/*"]\n')
        for _ in range(20):
            try:
                out.append(json.dumps(g["run"](pol, root=d, matrix_path=None), sort_keys=True, default=str))
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
    return (len(statements) - len(missing), len(statements))


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
        cov_covered, cov_total = coverage_of(module)
        eq = 0
        ev = []
        for line, fam, desc, msrc in specs:
            h = run(msrc, module)
            same = h == base and h not in ("", "TIMEOUT") and not h.startswith("ERR:")
            eq += 1 if same else 0
            ev.append({"line": line, "op": fam, "desc": desc, "equivalent": same})
        total_eq += eq
        pct = round(100.0 * cov_covered / cov_total, 1) if cov_total else None
        artifact["modules"][module] = {"survivors": len(specs), "equivalent": eq,
                                       "coverage_pct": pct, "coverage": f"{cov_covered}/{cov_total}", "evidence": ev}
        print(f"{module}: {len(specs)} survivors, {eq} eq, {len(specs)-eq} obs; corpus covers {cov_covered}/{cov_total} lines ({pct}%)")
    artifact["equivalent_total"] = total_eq
    outp = os.path.join(HERE, ".tmx", "oracle-e.json")
    json.dump(artifact, open(outp, "w"), indent=1)
    print(f"TOTAL equivalent: {total_eq}; artifact -> {outp}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", nargs=2, metavar=("SRC", "MODULE"))
    ap.add_argument("--matrix", default=os.path.join(HERE, ".tmx", "crit.json"))
    a = ap.parse_args()
    if a.worker:
        worker(a.worker[0], a.worker[1])
    else:
        measure(a.matrix)
