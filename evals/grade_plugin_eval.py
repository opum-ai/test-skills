#!/usr/bin/env python3
"""Objective grading of a `claude plugin eval` task run. plugin eval's graders only read what the
agent produced, so they cannot re-run the suite, re-collect kill matrices or run the hidden
acceptance tests. This runs evals/grade.py on every run's kept workspace (the eval must be run with
--keep-temp) and writes the per-run metrics beside the eval's own result.

  grade_plugin_eval.py <task.json> [--python PY] [--jobs N]
  -> <task>-objective.json (every run's grade.py output) and <task>-objective.md (a table)
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def workspace(run):
    """plugin eval --keep-temp leaves each run at <tmp>/e-XXXX/{out/trace.jsonl, sealed/home/cwd}, with
    sealed/ at mode 000. We own it, so open it just enough to read the workspace."""
    trace = run.get("tracePath") or ""
    if not trace:
        return None
    root = os.path.dirname(os.path.dirname(trace))
    for base in (os.path.join(root, "sealed"), root):
        if os.path.isdir(base) and not os.access(base, os.R_OK | os.X_OK):
            try:
                os.chmod(base, 0o700)
            except OSError:
                pass
        ws = os.path.join(base, "home", "cwd")
        if os.path.isdir(ws):
            return ws
    return None


def headline(case, g):
    """The few numbers that matter per case, for the table."""
    if "error" in g:
        return g["error"]
    if case == "shop-reduce":
        return (f"PR tier {g['pr_tier']['passed']} passed/{g['pr_tier']['failed']} failed; lost kills "
                f"{g['lost_kill_count']} of {g['kills_before']}; history bugs {g['history_mutants_killed']}/"
                f"{g['history_mutants_total']}; src unchanged {g['src_unchanged']}")
    if case == "loyalty-greenfield":
        m = g.get("mutation_new_code") or {}
        return (f"hidden {g['hidden_acceptance']['passed']}/{g['hidden_acceptance']['total']}; tests added "
                f"{g.get('tests_added')}; mutation {m.get('score')}; smells {sum((g.get('smells') or {}).values())}")
    if case == "constitution-setup":
        return (f"src unchanged {g['src_unchanged']}; retry loop left {g['ci_has_retry_loop']}; suite passes "
                f"{g['pr_suite_still_passes']}; new files {len(g['new_files'])}")
    return ", ".join(f"{k} {v}" for k, v in g.items() if k.endswith("unchanged"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task_json")
    ap.add_argument("--python", default=os.path.join(HERE, "..", ".venv", "bin", "python"))
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    a.python = os.path.abspath(a.python)   # grade.py runs from inside each workspace
    res = json.load(open(a.task_json))
    names = sorted((e["name"] for e in json.load(open(os.path.join(HERE, "evals.json")))["evals"]), key=len, reverse=True)
    jobs = []
    for c in res["cases"]:
        case = next((n for n in names if n in c["name"]), None)
        for arm, runs in (c["arms"].items() if isinstance(c["arms"], dict) else [("with", c["arms"])]):
            for i, run in enumerate(runs, 1):
                jobs.append((case, c["name"], arm, i, run))

    def grade(job):
        case, name, arm, i, run = job
        ws = workspace(run)
        if not case:
            return job, {"error": "no matching eval in evals.json"}
        if not ws:
            return job, {"error": "workspace not kept (run plugin eval with --keep-temp)"}
        p = subprocess.run([sys.executable, os.path.join(HERE, "grade.py"), case, ws, "--python", a.python],
                           capture_output=True, text=True)
        try:
            return job, json.loads(p.stdout)
        except json.JSONDecodeError:
            return job, {"error": f"grade.py failed: {(p.stderr or p.stdout).strip().splitlines()[-1:]}"}

    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        graded = list(ex.map(grade, jobs))
    out = [{"case": case, "eval_case": name, "arm": arm, "run": i, "score": run.get("score"),
            "workspace": workspace(run), "objective": g} for (case, name, arm, i, run), g in graded]
    base = os.path.splitext(a.task_json)[0]
    json.dump(out, open(base + "-objective.json", "w"), indent=1)
    lines = ["| Case | Arm | Run | Judge score | Objective (grade.py) |", "|---|---|---|---|---|"]
    lines += [f"| {o['case']} | {o['arm']} | {o['run']} | {o['score']:.2f} | {headline(o['case'], o['objective'])} |"
              for o in out]
    open(base + "-objective.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
