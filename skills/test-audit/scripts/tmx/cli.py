"""Command-line dispatch for tmx.py."""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import sys

from . import cover, matrix as mx


def _analyze(a) -> int:
    m = mx.load(a.matrix)
    obl = mx.obligations(m, lines=a.lines)
    tests = sorted(m["tests"])
    sets = mx.per_test(obl, tests)
    if a.objective == "time":
        cost = {t: max(1e-4, float(m["tests"][t].get("duration", 0.0))) for t in tests}
    else:  # count, with a tiny runtime tie-break so equal-count covers prefer faster tests
        cost = {t: 1.0 + 1e-6 * float(m["tests"][t].get("duration", 0.0)) for t in tests}
    if not any(obl.values()):
        print("refusing to plan a reduction: the matrix has no obligations (no killed mutants"
              + (" or covered lines" if a.lines else "") + "). A matrix that measures nothing would "
              "certify deleting every test. Collect with mutation enabled, and check that the tests import --src.")
        return 2
    forced = [t for t in tests if any(fnmatch.fnmatch(t, g) for g in a.keep)]
    inst = cover.Instance(sorted(obl), sets, cost)
    res = cover.solve(inst, forced=forced, node_budget=a.node_budget, time_budget_s=a.time_budget)
    keep = res["keep"]
    witness, missing = cover.certificate(inst, keep)
    removed = cover.classify_removed(inst, keep)
    before = mx.mutation_score(m)
    after = mx.mutation_score(m, keep)
    dur = lambda ts: round(sum(float(m["tests"][t].get("duration", 0.0)) for t in ts), 4)  # noqa: E731
    plan = {
        "schema": "reduction-plan/1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "matrix": {"path": a.matrix, "commit": m.get("commit"), "tool": m.get("tool"), "scope": m.get("scope")},
        "preserves": ["killed mutants"] + (["covered lines"] if a.lines else []),
        "objective": a.objective,
        "forced": forced,
        "before": {"tests": len(tests), "duration_s": dur(tests), "mutation": before},
        "after": {"tests": len(keep), "duration_s": dur(keep), "mutation": after},
        "optimal": res["optimal"],
        "lower_bound": res["lower_bound"] if a.objective == "time" else int(round(res["lower_bound"] + 0.4999)),
        "solver": res["stats"],
        "keep": keep,
        "remove": removed,
        "curve": [[n, f] for n, f, _ in cover.curve(inst)],
        "certificate": witness,
        "uncovered": missing,
    }
    with open(a.out, "w") as f:
        json.dump(plan, f, indent=1, sort_keys=True)
        f.write("\n")
    if a.csv:
        import csv
        unique = {t: 0 for t in tests}
        for o, ks in obl.items():
            if len(ks) == 1:
                unique[next(iter(ks))] += 1
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["test", "verdict", "reason", "kills", "unique_kills", "covered_by", "seconds"])
            for t in tests:
                r = removed.get(t, {})
                by = r.get("by") or r.get("of") or ""
                w.writerow([t, "keep" if t in keep else "remove", "forced" if t in forced else r.get("reason", "needed"),
                            len(sets.get(t, ())), unique[t], " ".join(by) if isinstance(by, list) else by,
                            m["tests"][t].get("duration", "")])
    reasons = {}
    for r in removed.values():
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    print(f"tests: {len(tests)} -> {len(keep)} ({len(tests) - len(keep)} removable: "
          + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) + ")")
    print(f"runtime: {plan['before']['duration_s']}s -> {plan['after']['duration_s']}s")
    print(f"mutation score: {_pct(before)} -> {_pct(after)} over {before['mutants']} mutants "
          f"({'optimal' if res['optimal'] else 'best found; lower bound ' + str(plan['lower_bound'])})")
    cv = plan["curve"]
    marks = [next((n for n, f in cv if f >= q), None) for q in (0.8, 0.9, 0.95)]
    print("trade-off: " + ", ".join(f"{int(q * 100)}% of obligations with {n} tests"
                                     for q, n in zip((0.8, 0.9, 0.95), marks) if n))
    print(f"certificate: {len(witness)} obligations witnessed, {len(missing)} missing -> {a.out}")
    return 0 if not missing else 3


def _pct(s: dict) -> str:
    return "n/a" if s["score"] is None else f"{100 * s['score']:.1f}%"


def _verify(a) -> int:
    with open(a.plan) as f:
        plan = json.load(f)
    m = mx.load(a.matrix)
    lines = "covered lines" in plan.get("preserves", [])
    obl = mx.obligations(m, lines=lines)
    keep = set(plan["keep"])
    unknown = sorted(keep - set(m["tests"]))
    problems = cover.check_certificate(obl, keep, plan.get("certificate", {}))
    problems += [f"retained test {t} is not in the matrix" for t in unknown]
    if m.get("commit") and plan["matrix"].get("commit") and m["commit"] != plan["matrix"]["commit"]:
        problems.append(f"plan was built from commit {plan['matrix']['commit']}, matrix is {m['commit']}")
    if problems:
        print(f"INVALID: {len(problems)} problem(s)")
        for p in problems[:50]:
            print("  " + p)
        return 3
    n = sum(1 for k in obl.values() if k)
    if getattr(a, "rerun", False):
        from . import pycollect
        r = pycollect.rerun_certificate(a.root, m, plan, python=a.python, jobs=a.jobs)
        if not r["valid"]:
            print("INVALID (empirical): " + json.dumps(r)[:3000])
            return 3
        print(f"replayed {r['replayed']} obligations against the retained suite alone: all caught")
    print(f"VALID: all {n} obligations ({', '.join(plan['preserves'])}) are discharged by the "
          f"{len(keep)} retained tests")
    return 0


def _score(a) -> int:
    m = mx.load(a.matrix)
    s = mx.mutation_score(m)
    by_status = {}
    for mu in m["mutants"].values():
        by_status[mu.get("status")] = by_status.get(mu.get("status"), 0) + 1
    zero = [t for t in m["tests"] if not any(t in mu.get("killed_by", []) for mu in m["mutants"].values())]
    lines = {ln for cov in m["coverage"].values() for ln in cov}
    print(json.dumps({"tests": len(m["tests"]), "mutation": s, "mutants_by_status": by_status,
                      "zero_kill_tests": len(zero), "covered_lines": len(lines),
                      "duration_s": round(sum(float(t.get('duration', 0)) for t in m["tests"].values()), 4)},
                     indent=1))
    if a.survivors:
        for mid, mu in sorted(m["mutants"].items()):
            if mu.get("status") in ("survived", "no_coverage"):
                print(f"{mu['status']:12} {mu.get('key') or mu['file'] + ':' + str(mu['line']) + ' ' + str(mu.get('desc', ''))}")
    return 0


def main(argv) -> int:
    p = argparse.ArgumentParser(prog="tmx.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect-pytest", help="per-test coverage + kill matrix for a pytest project")
    c.add_argument("--root", default=".")
    c.add_argument("--src", action="append", required=True, help="source path to measure and mutate (repeatable)")
    c.add_argument("--tests", action="append", default=[], help="test path(s) passed to pytest")
    c.add_argument("-o", "--out", default=".tmx/matrix.json")
    c.add_argument("--python", default=sys.executable)
    c.add_argument("--jobs", type=int, default=4)
    c.add_argument("--no-mutate", action="store_true")
    c.add_argument("--max-mutants", type=int, default=0, help="deterministic sample size (0 = all)")
    c.add_argument("--timeout-factor", type=float, default=5.0)
    c.add_argument("--operators", default=None, help="comma list; default cmp,arith,bool,not,const,return,cond,stmt,raise,call,round; add 'extreme' for "
                        "whole-body removal, or use only 'extreme' for a cheap pseudo-tested-function pass")
    c.add_argument("--pytest-arg", action="append", default=[])
    c.add_argument("--per-line", type=int, default=0, help="at most N mutants per source line (Google-style sampling)")
    c.add_argument("--history", type=int, default=0, help="add up to N real-fault mutants by reverting past fix commits")
    c.add_argument("--extra-mutants", help='JSON list of domain faults: [{"file","find","replace","desc"}]')

    s = sub.add_parser("import-stryker", help="convert a Stryker mutation-testing-report JSON")
    s.add_argument("report")
    s.add_argument("-o", "--out", default=".tmx/matrix.json")
    s.add_argument("--allow-bail", action="store_true", help="accept a report run without disableBail")
    s.add_argument("--allow-low-score", action="store_true", help="accept a report that looks vacuous")

    pi = sub.add_parser("import-pit", help="convert a PIT mutations.xml (run with -DfullMutationMatrix=true)")
    pi.add_argument("report")
    pi.add_argument("-o", "--out", default=".tmx/matrix.json")

    sc = sub.add_parser("score", help="mutation score and suite stats")
    sc.add_argument("matrix")
    sc.add_argument("--survivors", action="store_true", help="list surviving / uncovered mutants")

    an = sub.add_parser("analyze", help="minimal kill-preserving subset with a certificate")
    an.add_argument("matrix")
    an.add_argument("-o", "--out", default=".tmx/plan.json")
    an.add_argument("--lines", action="store_true", help="also preserve every covered line")
    an.add_argument("--objective", choices=["count", "time"], default="count")
    an.add_argument("--keep", action="append", default=[], help="glob of test ids that must be retained")
    an.add_argument("--node-budget", type=int, default=200_000)
    an.add_argument("--time-budget", type=float, default=20.0)
    an.add_argument("--csv", help="also write a per-test keep/remove table the user can act on directly")

    v = sub.add_parser("verify", help="independently check a reduction plan's certificate")
    v.add_argument("plan")
    v.add_argument("matrix")
    v.add_argument("--rerun", action="store_true",
                   help="also replay every obligation's mutant against the retained suite (empirical check)")
    v.add_argument("--root", default=".")
    v.add_argument("--python", default=sys.executable)
    v.add_argument("--jobs", type=int, default=4)

    sm = sub.add_parser("smells", help="static test-smell scan (Python AST; heuristic for other languages)")
    sm.add_argument("paths", nargs="+")
    sm.add_argument("-o", "--out")
    sm.add_argument("--src", action="append", default=[], help="source roots, to spot private-API coupling")

    cl = sub.add_parser("clones", help="cluster structurally identical tests (parametrize / property candidates)")
    cl.add_argument("paths", nargs="+")
    cl.add_argument("-o", "--out")
    cl.add_argument("--min-size", type=int, default=3)

    cv = sub.add_parser("covering", help="check or generate t-way coverage of a declared input partition model")
    cv.add_argument("model")
    cv.add_argument("--strength", type=int, default=2)
    cv.add_argument("--generate", action="store_true", help="emit a small covering array for the model")

    g = sub.add_parser("gate", help="CI gate: enforce the project's test policy")
    g.add_argument("--policy", default="test-policy.toml")
    g.add_argument("--matrix")
    g.add_argument("--junit", action="append", default=[])
    g.add_argument("--base", help="git ref to diff against for per-PR rules")
    g.add_argument("--root", default=".")
    g.add_argument("--json", action="store_true")
    g.add_argument("--policy-source", choices=["base", "head"],
                   help="where to read policy+baseline; default 'base' when --base is given (anti-tamper)")

    su = sub.add_parser("subsumes", help="do the --by tests kill every mutant the --tests tests kill? (exit 3 if not)")
    su.add_argument("matrix")
    su.add_argument("--by", action="append", required=True, help="glob of the subsuming tests (e.g. a property)")
    su.add_argument("--tests", action="append", required=True, help="glob of the tests claimed redundant")

    cp = sub.add_parser("compare", help="obligations a new matrix lost relative to an old one (exit 3 if any)")
    cp.add_argument("before")
    cp.add_argument("after")

    pr = sub.add_parser("probation", help="demote-before-delete: add, install hook, record nightly runs, prune")
    pr.add_argument("action", choices=["add", "install", "record", "status", "prune"])
    pr.add_argument("--plan", help="plan.json (for add)")
    pr.add_argument("--file", default=".test-probation.json")
    pr.add_argument("--conftest", default="conftest.py", help="for install")
    pr.add_argument("--junit", action="append", default=[], help="nightly JUnit (for record)")
    pr.add_argument("--days", type=int, default=14)
    pr.add_argument("--min-runs", type=int, default=20)
    pr.add_argument("--root", default=".")
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--python", default=sys.executable, help="interpreter for `pytest --collect-only` (prune)")
    pr.add_argument("--policy", default="test-policy.toml", help="probation floors come from here (prune)")

    b = sub.add_parser("baseline", help="record the accepted suite state for the gate's ratchet")
    b.add_argument("--junit", action="append", default=[])
    b.add_argument("--matrix")
    b.add_argument("--root", default=".")
    b.add_argument("-o", "--out", default=".test-baseline.json")

    a = p.parse_args(argv)
    if a.cmd == "subsumes":
        m = mx.load(a.matrix)
        by = {t for t in m["tests"] if any(fnmatch.fnmatch(t, g) for g in a.by)}
        ex = {t for t in m["tests"] if any(fnmatch.fnmatch(t, g) for g in a.tests)} - by
        if not by or not ex:
            print(f"no tests matched: --by {len(by)}, --tests {len(ex)}")
            return 2
        kills = lambda ts: {k for k, mu in m["mutants"].items()  # noqa: E731
                            if mu.get("status") == "killed" and ts & set(mu.get("killed_by", []))}
        kb, ke = kills(by), kills(ex)
        missing = sorted(ke - kb)
        out = {"subsuming_tests": sorted(by), "claimed_redundant": len(ex), "their_kills": len(ke),
               "subsumer_kills": len(kb), "not_covered_by_subsumer": [
                   f"{m['mutants'][k]['file']}:{m['mutants'][k]['line']} {m['mutants'][k].get('op')} "
                   f"{m['mutants'][k].get('desc')}" for k in missing],
               "verdict": "SUBSUMED" if not missing else "NOT SUBSUMED"}
        print(json.dumps(out, indent=1))
        return 0 if not missing else 3
    if a.cmd == "compare":
        from . import probation
        r = probation.compare(mx.load(a.before), mx.load(a.after))
        print(json.dumps(r, indent=1))
        return 3 if r["lost"] or r["not_in_new_matrix"] else 0
    if a.cmd == "probation":
        from . import probation
        if a.action == "add":
            if not a.plan:
                p.error("probation add needs --plan")
            r = probation.add(a.plan, a.file)
        elif a.action == "install":
            r = {"hook": probation.install_hook(a.conftest)}
        elif a.action == "record":
            r = probation.record(a.file, a.junit)
        elif a.action == "status":
            import os
            es = json.load(open(a.file)) if os.path.exists(a.file) else []
            r = {"entries": len(es), "due": len(probation.due(es, a.days, a.min_runs)),
                 "failed_ever": [e["test"] for e in es if e["failures"]]}
        else:
            import os
            days, runs = a.days, a.min_runs
            pol = os.path.join(a.root, a.policy)
            if os.path.exists(pol):   # the policy's (rigor-derived) probation window is a floor
                from . import gate, rigor
                policy = gate.load_policy(pol)
                lv = rigor.highest([policy.get("rigor", "R3"),
                                    *[t.get("rigor") for t in policy.get("adequacy", {}).get("tier", [])]])
                R = rigor.rules(lv, policy)
                days, runs = max(days, R["probation_days"]), max(runs, R["probation_runs"])
            r = probation.prune(a.root, a.file, days, runs, dry=a.dry_run,
                                collected=probation.collected_ids(a.root, a.python))
            r["window"] = {"days": days, "min_runs": runs}
        print(json.dumps(r, indent=1))
        return 1 if r.get("failed") or r.get("failed_ever") else 0
    if a.cmd == "baseline":
        from . import gate
        if not a.junit and not a.matrix:
            p.error("baseline needs --junit and/or --matrix")
        r = gate.write_baseline(a.root, a.out, a.junit, a.matrix)
        print(f"baseline: {r['tests']} tests, {r['seconds']}s ({r['id_source']} ids) -> {a.out}")
        return 0
    if a.cmd == "collect-pytest":
        from . import pycollect, mutate_py
        ops = a.operators.split(",") if a.operators else mutate_py.OPERATORS
        import os
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        m = pycollect.collect(a.root, a.src, a.tests, a.out, python=a.python, mutate=not a.no_mutate,
                              jobs=a.jobs, timeout_factor=a.timeout_factor, max_mutants=a.max_mutants,
                              operators=ops, pytest_args=a.pytest_arg, per_line=a.per_line, history=a.history,
                              extra=json.load(open(a.extra_mutants)) if a.extra_mutants else None,
                              log=lambda s: print(s, file=sys.stderr))
        s = mx.mutation_score(m)
        print(f"{len(m['tests'])} tests, {s['mutants']} mutants, score {_pct(s)} -> {a.out}")
        return 0
    if a.cmd == "import-stryker":
        from . import importers
        return importers.stryker(a.report, a.out, a.allow_bail, a.allow_low_score)
    if a.cmd == "import-pit":
        from . import importers
        return importers.pit(a.report, a.out)
    if a.cmd == "score":
        return _score(a)
    if a.cmd == "analyze":
        return _analyze(a)
    if a.cmd == "verify":
        return _verify(a)
    if a.cmd == "smells":
        from . import smells
        return smells.main(a)
    if a.cmd == "clones":
        from . import smells
        return smells.clones_main(a)
    if a.cmd == "covering":
        from . import covering
        return covering.main(a)
    if a.cmd == "gate":
        from . import gate
        return gate.main(a)
    return 2
