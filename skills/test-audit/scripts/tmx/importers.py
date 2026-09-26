"""Importers from other tools' reports into the test matrix.

Stryker (JS/TS, C#, Scala) writes the mutation-testing-elements schema
(https://github.com/stryker-mutator/mutation-testing-elements). With
`coverageAnalysis: "perTest"` each mutant carries `killedBy` and `coveredBy` test ids, which
is exactly a kill matrix.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from . import matrix as mx

STATUS = {"Killed": "killed", "Survived": "survived", "NoCoverage": "no_coverage", "Timeout": "timeout",
          "CompileError": "error", "RuntimeError": "error", "Ignored": "ignored", "Pending": "error"}


def stryker(report_path: str, out: str) -> int:
    with open(report_path) as f:
        r = json.load(f)
    tests = {}
    names = {}
    for tfile, tf in (r.get("testFiles") or {}).items():
        for t in tf.get("tests", []):
            tid = f"{tfile}::{t.get('name', t['id'])}"
            names[t["id"]] = tid
            tests[tid] = {"file": tfile, "outcome": "passed"}
    mutants = {}
    for sfile, sf in r.get("files", {}).items():
        for mu in sf.get("mutants", []):
            killed = [names.get(i, i) for i in (mu.get("killedBy") or [])]
            covered = [names.get(i, i) for i in (mu.get("coveredBy") or [])]
            for t in killed + covered:
                tests.setdefault(t, {"file": t.split("::")[0], "outcome": "passed"})
            loc = mu.get("location", {}).get("start", {})
            mutants[f"{sfile}#{mu['id']}"] = {
                "file": sfile, "line": loc.get("line"), "op": mu.get("mutatorName"),
                "desc": mu.get("replacement", ""), "status": STATUS.get(mu.get("status"), "error"),
                "killed_by": sorted(killed), "covered_by": sorted(covered)}
    if not any(mu["killed_by"] for mu in mutants.values()):
        print("warning: no killedBy data; run Stryker with coverageAnalysis: 'perTest' "
              "and the json reporter", flush=True)
    m = {"schema": mx.SCHEMA, "root": os.getcwd(), "commit": None,
         "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "tool": {"collector": "stryker", "mutator": "stryker", "operators": []},
         "scope": {}, "tests": tests, "coverage": {}, "mutants": mutants}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    mx.save(m, out)
    s = mx.mutation_score(m)
    print(f"{len(tests)} tests, {s['mutants']} mutants, score "
          f"{'n/a' if s['score'] is None else round(100 * s['score'], 1)}% -> {out}")
    return 0


PIT_STATUS = {"KILLED": "killed", "SURVIVED": "survived", "NO_COVERAGE": "no_coverage",
              "TIMED_OUT": "timeout", "MEMORY_ERROR": "killed", "RUN_ERROR": "error", "NON_VIABLE": "error"}


def pit(report_path: str, out: str) -> int:
    """PIT mutations.xml, run with -DfullMutationMatrix=true so <killingTests> lists every killer."""
    import xml.etree.ElementTree as ET
    root = ET.parse(report_path).getroot()
    tests, mutants = {}, {}
    split = lambda s: [t for t in (s or "").split("|") if t]  # noqa: E731
    for i, mu in enumerate(root.iter("mutation")):
        killed = split(mu.findtext("killingTests"))
        survived_by = split(mu.findtext("succeedingTests"))
        for t in killed + survived_by:
            tests.setdefault(t, {"file": t.split("[")[0].split("(")[0], "outcome": "passed"})
        src = mu.findtext("sourceFile") or ""
        cls = mu.findtext("mutatedClass") or ""
        path = cls.rsplit(".", 1)[0].replace(".", "/") + "/" + src if "." in cls else src
        mutants[f"pit{i:05d}"] = {
            "file": path, "line": int(mu.findtext("lineNumber") or 0),
            "op": (mu.findtext("mutator") or "").rsplit(".", 1)[-1], "desc": mu.findtext("description") or "",
            "status": PIT_STATUS.get(mu.get("status", ""), "error"),
            "killed_by": sorted(killed), "covered_by": sorted(set(killed) | set(survived_by))}
    if mutants and not any(m["killed_by"] for m in mutants.values()):
        print("warning: no killingTests; re-run PIT with -DfullMutationMatrix=true -DoutputFormats=XML")
    m = {"schema": mx.SCHEMA, "root": os.getcwd(), "commit": None,
         "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "tool": {"collector": "pit", "mutator": "pit", "operators": []},
         "scope": {}, "tests": tests, "coverage": {}, "mutants": mutants}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    mx.save(m, out)
    s = mx.mutation_score(m)
    print(f"{len(tests)} tests, {s['mutants']} mutants -> {out}")
    return 0
