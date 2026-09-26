"""CI gate: enforce the machine-checkable articles of the project's test constitution.

Reads test-policy.toml, plus whatever evidence the CI job provides:
  --junit      JUnit XML from the test run (count and wall time; universal across runners)
  --matrix     a tmx test matrix (mutation adequacy per tier, marginal-value admission)
  --base       git ref of the PR base (changed test files, new tests, Test-Budget trailers)
and the committed baseline `.test-baseline.json` (test ids and totals at the last accepted state).

Every violation names its article. Exit 0 = pass, 1 = violations, 2 = bad policy.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set

from . import matrix as mx
from . import rigor


# ------------------------------------------------------------------ policy loading

def _has_tomllib() -> bool:
    try:
        import tomllib  # noqa: F401
        return True
    except ImportError:
        return False


def load_policy(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(raw.decode())
    except ImportError:
        return mini_toml(raw.decode())


def mini_toml(text: str) -> dict:
    """Subset of TOML sufficient for test-policy.toml on Python < 3.11: tables, arrays of
    tables, strings, numbers, booleans, flat arrays and inline tables of scalars."""
    root: dict = {}
    cur = root
    for lineno, line in enumerate(text.splitlines(), 1):
        line = _strip_comment(line).strip()
        if not line:
            continue
        if line.startswith("[["):
            keys = line[2:-2].strip().split(".")
            parent = _descend(root, keys[:-1])
            parent.setdefault(keys[-1], []).append({})
            cur = parent[keys[-1]][-1]
        elif line.startswith("["):
            cur = _descend(root, line[1:-1].strip().split("."))
        else:
            k, _, v = line.partition("=")
            cur[k.strip().strip('"')] = _value(v.strip(), lineno)
    return root


def _strip_comment(line: str) -> str:
    out, q = [], None
    for ch in line:
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _descend(d: dict, keys: List[str]) -> dict:
    for k in keys:
        nxt = d.setdefault(k.strip().strip('"'), {})
        d = nxt[-1] if isinstance(nxt, list) else nxt
    return d


def _split_top(s: str) -> List[str]:
    parts, depth, q, buf = [], 0, None, ""
    for ch in s:
        if q:
            buf += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _value(v: str, lineno: int):
    if v.startswith(("\"", "'")):
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    if v.startswith("["):
        return [_value(x, lineno) for x in _split_top(v[1:-1])]
    if v.startswith("{"):
        return {kv.partition("=")[0].strip(): _value(kv.partition("=")[2].strip(), lineno)
                for kv in _split_top(v[1:-1])}
    try:
        return int(v.replace("_", ""))
    except ValueError:
        try:
            return float(v)
        except ValueError:
            raise SystemExit(f"test-policy.toml:{lineno}: cannot parse value {v!r}")


# ------------------------------------------------------------------ evidence

def junit_totals(paths: List[str]) -> dict:
    ids: Set[str] = set()
    seconds = 0.0
    failed = skipped = 0
    for p in paths:
        root = ET.parse(p).getroot()
        for tc in root.iter("testcase"):
            ids.add(f"{tc.get('classname', '')}::{tc.get('name', '')}")
            seconds += float(tc.get("time") or 0)
            if tc.find("failure") is not None or tc.find("error") is not None:
                failed += 1
            if tc.find("skipped") is not None:
                skipped += 1
    return {"ids": ids, "tests": len(ids), "seconds": round(seconds, 3), "failed": failed, "skipped": skipped}


def _git(root: str, *args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    except Exception:
        return ""


def _changed(root: str, base: str, diff_filter: str = "") -> List[str]:
    """Changed files relative to --root (git reports paths from the repo top; renames count)."""
    args = ["diff", "--name-only", "-M", f"{base}...HEAD", "--relative"]
    if diff_filter:
        args.insert(2, f"--diff-filter={diff_filter}")
    return _git(root, *args).split()


def _touched_lines(root: str, base: str, files: List[str]) -> Dict[str, Set[int]]:
    """Lines added or changed on the PR side, per file; only tests overlapping them are judged."""
    out: Dict[str, Set[int]] = {}
    cur = None
    for line in _git(root, "diff", "-U0", "-M", "--relative", f"{base}...HEAD", "--", *files).splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            out.setdefault(cur, set())
        elif line.startswith("@@") and cur:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, n = int(m.group(1)), int(m.group(2) or 1)
            out[cur].update(range(start, start + n))
    return out


def _load_list(path: str) -> list:
    try:
        return json.load(open(path)) if os.path.exists(path) else []
    except ValueError:
        return []


def _load_list_text(text: str) -> list:
    try:
        return json.loads(text) if text.strip() else []
    except ValueError:
        return []


def _match(path: str, globs: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


# ------------------------------------------------------------------ the gate

def _tier_of(path: str, tiers: List[dict]) -> Optional[dict]:
    return next((t for t in tiers if _match(path, t.get("paths", []))), None)


def _approvers(policy: dict) -> Optional[Set[str]]:
    """Approvals come from CI (the code host's review record), never from text the author wrote."""
    raw = os.environ.get("TMX_PR_APPROVERS")
    if raw is None:
        return None
    got = {x.strip().lstrip("@").lower() for x in raw.split(",") if x.strip()}
    allowed = {x.strip().lstrip("@").lower() for x in policy.get("assurance", {}).get("approvers", [])}
    return got & allowed if allowed else got


def run(policy: dict, root: str = ".", junit: List[str] = (), matrix_path: Optional[str] = None,
        base: Optional[str] = None, pr_body: str = "") -> dict:
    v: List[dict] = []
    info: Dict[str, object] = {}
    add = lambda art, rule, msg: v.append({"article": art, "rule": rule, "message": msg})  # noqa: E731

    budget = policy.get("budget", {})
    tiers = policy.get("adequacy", {}).get("tier", [])
    baseline_path = os.path.join(root, policy.get("baseline", ".test-baseline.json"))
    if policy.get("_from_base"):   # the base branch's accepted state; never the PR's own copy
        baseline = json.loads(policy["_baseline_text"]) if policy.get("_baseline_text") else None
        info["policy_source"] = "base"
    else:
        baseline = json.load(open(baseline_path)) if os.path.exists(baseline_path) else None
    trailers = pr_body
    changed_all: List[str] = []
    if base:
        if not _git(root, "rev-parse", "--verify", "--quiet", base + "^{commit}").strip():
            raise SystemExit(f"gate: base ref {base!r} not found (fetch it first, e.g. "
                             f"`git fetch origin {base.split('/')[-1]}`)")
        trailers += _git(root, "log", "--format=%B", f"{base}..HEAD")
        changed_all = _changed(root, base)

    # Effective rigor: max(project default, tiers of touched paths, declared trailer). A changed
    # test file counts as touching every source file its tests cover (from the matrix).
    touched_files = set(changed_all)
    if base and matrix_path and os.path.exists(matrix_path):
        mm = mx.load(matrix_path)
        for t, cov in mm["coverage"].items():
            if t.split("::", 1)[0] in touched_files:
                touched_files.update(ln.rsplit(":", 1)[0] for ln in cov)
    touched_tiers = {(_tier_of(f, tiers) or {}).get("rigor") for f in touched_files}
    if not base:  # no diff to scope by: the whole policy is in play
        touched_tiers = {t.get("rigor") for t in tiers}
    level = rigor.highest([policy.get("rigor", "R3"), rigor.declared(trailers), *touched_tiers])
    R = rigor.rules(level, policy)
    info["rigor"] = f"{R['level']} {R['name']}"
    approvers = _approvers(policy)
    justified = re.search(r"^Test-Budget:\s*\S.+$", trailers, re.M | re.I) is not None
    info["test_budget_trailer"] = justified

    # Article XIII / R-4 - accountable approval (R5 always; R4 for budget exceptions)
    if R["approval_required"]:
        if approvers is None:
            add("XIII", "approval", f"{R['level']} requires an accountable approval, and none was supplied: CI must "
                                    "set TMX_PR_APPROVERS from the code host's review record")
        elif not approvers:
            add("XIII", "approval", f"{R['level']}: no approval from a listed approver "
                                    f"({', '.join(policy.get('assurance', {}).get('approvers', [])) or 'any reviewer'})")

    # State files: demotions and quarantines hide tests from the PR tier, so a change that adds
    # entries is judged against the base branch's lists, and every new entry must be justified.
    fl = policy.get("flaky", {})
    qname = fl.get("quarantine_file", ".test-quarantine.json")
    pname = ".test-probation.json"
    head_q, head_p = _load_list(os.path.join(root, qname)), _load_list(os.path.join(root, pname))
    if base:
        base_q, base_p = _load_list_text(_git(root, "show", f"{base}:{qname}")), \
            _load_list_text(_git(root, "show", f"{base}:{pname}"))
        new_q = [e for e in head_q if e.get("test") not in {x.get("test") for x in base_q}]
        new_p = [e for e in head_p if e.get("test") not in {x.get("test") for x in base_p}]
        for e in new_q:
            if not (e.get("issue") and e.get("owner")):
                add("XI", "quarantine_entry", f"{e.get('test')} newly quarantined without an owner and an issue link")
            elif R["budget_exception"] == "approval" and not approvers:
                add("XI", "quarantine_entry", f"{e.get('test')}: at {R['level']} quarantining needs a listed approver")
        info["new_quarantine"], info["new_probation"] = len(new_q), len(new_p)
    else:
        new_p = []
    demoted = {e.get("test") for e in head_p} | {e.get("test") for e in head_q}

    # Article II - budget (demoted and quarantined tests still count until they are deleted)
    totals = junit_totals(list(junit)) if junit else None
    if totals:
        hidden = len(demoted)
        total_tests = totals["tests"] + hidden
        info.update({"tests": totals["tests"], "hidden_tests": hidden, "seconds": totals["seconds"],
                     "skipped": totals["skipped"]})
        if budget.get("max_tests") is not None and total_tests > budget["max_tests"]:
            add("II", "max_tests", f"{total_tests} tests ({totals['tests']} in this run + {hidden} on probation or "
                                   f"quarantine) exceeds the budget of {budget['max_tests']}; "
                                   "reduce (test-reduce) or amend the constitution")
        if budget.get("max_suite_seconds") is not None and totals["seconds"] > budget["max_suite_seconds"]:
            add("II", "max_suite_seconds", f"suite takes {totals['seconds']}s, budget {budget['max_suite_seconds']}s")
        if baseline and budget.get("max_new_tests_per_pr") is not None:
            # Compare like with like: the baseline counts the PR-tier run plus demoted tests.
            grown = total_tests - int(baseline.get("tests", 0)) - int(baseline.get("hidden_tests", 0))
            info["growth"] = grown
            if grown > budget["max_new_tests_per_pr"]:
                if not justified:
                    add("II", "max_new_tests_per_pr",
                        f"+{grown} tests (limit {budget['max_new_tests_per_pr']} per change without a "
                        "`Test-Budget: <reason>` trailer in the PR body or a commit message)")
                elif R["budget_exception"] == "approval" and not approvers:
                    add("II", "max_new_tests_per_pr",
                        f"+{grown} tests: at {R['level']} a Test-Budget exception also needs a listed approver's "
                        "approval (TMX_PR_APPROVERS from the review record)")
        max_skip = policy.get("flaky", {}).get("max_skipped")
        if max_skip is not None and totals["skipped"] > max_skip:
            add("XI", "max_skipped", f"{totals['skipped']} skipped tests, limit {max_skip}")

    # Article IV / VI / X - smells in the tests this change touched
    forbid = set(R["forbid_smells"])
    if base and (forbid or R["max_mocks_per_test"] is not None):
        roots = policy.get("test_roots")   # judge only the project's own suites (not fixtures or vendored code)
        changed = [f for f in _changed(root, base, "AMR")
                   if re.search(r"(test_.*\.py|_test\.py|\.(test|spec)\.[jt]sx?)$", f)
                   and (not roots or any(f == r.rstrip("/") or f.startswith(r.rstrip("/") + "/") for r in roots))]
        info["changed_test_files"] = changed
        if changed:
            from . import smells
            items = []
            for f in changed:
                p = os.path.join(root, f)
                if os.path.exists(p):
                    items += smells.py_smells(p, policy.get("source", [])) if p.endswith(".py") else smells.js_smells(p)
            touched = _touched_lines(root, base, changed)
            items = [s for s in items if any(ln in touched.get(os.path.relpath(s["file"], root), set())
                                             for ln in range(s.get("start", s["line"]), (s.get("end") or s["line"]) + 1))]
            for s in items:
                if s["smell"] in forbid:
                    add("IV" if s["smell"] in ("no-assertion", "tautology", "swallowed-exception") else
                        "VI" if s["smell"] in ("implementation-coupled", "snapshot-literal") else "X",
                        f"smell:{s['smell']}", f"{os.path.relpath(s['test'], root)}: {s['detail']}")
                if s["smell"] in ("mock-heavy", "mocks") and R["max_mocks_per_test"] is not None:
                    n = int(re.match(r"(\d+)", s["detail"]).group(1))
                    if n > R["max_mocks_per_test"]:
                        add("VI", "max_mocks_per_test", f"{os.path.relpath(s['test'], root)}: {s['detail']} "
                                                        f"(limit {R['max_mocks_per_test']} at {R['level']})")

    # Article III - risk-tiered adequacy; Article V - marginal value of new tests
    if matrix_path:
        m = mx.load(matrix_path)
        claimed: Set[str] = set()
        tier_scores = {}
        triage_path = os.path.join(root, policy.get("assurance", {}).get("triage_file", "testing/survivors.json"))
        triage = json.load(open(triage_path)) if os.path.exists(triage_path) else {}
        default_level = rigor.highest([policy.get("rigor", "R3")])
        for tier in tiers:  # first matching tier wins, so list critical tiers first
            mids = [k for k, mu in m["mutants"].items()
                    if k not in claimed and _match(mu.get("file", ""), tier.get("paths", []))]
            claimed.update(mids)
            sub = dict(m, mutants={k: m["mutants"][k] for k in mids})
            s = mx.mutation_score(sub)
            t_level = rigor.highest([default_level, tier.get("rigor")])
            TR = rigor.rules(t_level, policy)
            s["rigor"] = t_level
            tier_scores[tier.get("name", "?")] = s
            need = tier.get("min_mutation_score")
            floor_applies = tier.get("rigor") or rigor.LEVELS.index(default_level) >= 3  # R4+ projects: every tier
            if floor_applies and TR["min_mutation_score"] is not None:  # a level's floor only rises
                need = max(need or 0.0, TR["min_mutation_score"])
            if need is not None and s["score"] is not None and s["score"] + 1e-9 < need:
                add("III", f"tier:{tier.get('name')}",
                    f"mutation score {100 * s['score']:.1f}% < {100 * need:.0f}% on {s['mutants']} mutants "
                    f"in tier '{tier.get('name')}' ({t_level})")
            for k in mids:
                mu = m["mutants"][k]
                in_change = not base or mu.get("file") in changed_all
                if TR["triage_survivors"] and in_change and mu.get("status") in ("survived", "no_coverage"):
                    key = mu.get("key") or f"{mu['file']}:{mu['line']}:{mu.get('op')}:{mu.get('desc')}"
                    t = triage.get(key)
                    if not t or t.get("verdict") != "equivalent" or not t.get("reason"):
                        add("III", "triage_survivors", f"{t_level}: surviving mutant {key} is neither killed nor "
                                                      f"triaged as equivalent with a reason in {os.path.relpath(triage_path, root)}")
                if TR["history_must_be_killed"] and mu.get("op") == "history" and mu.get("status") != "killed":
                    add("III", "history_must_be_killed",
                        f"{t_level}: a past real fault is not caught by the suite: {mu.get('desc')} ({mu['file']})")
        info["tiers"] = tier_scores
        # Article XII - a new demotion must be certified: everything the demoted tests kill is
        # still killed by tests that stay in the PR tier.
        if new_p:
            stay = set(m["tests"]) - demoted
            lost = [k for k, mu in m["mutants"].items() if mu.get("status") == "killed"
                    and set(mu.get("killed_by", [])) & {e.get("test") for e in new_p}
                    and not set(mu.get("killed_by", [])) & stay]
            if lost:
                add("XII", "uncertified_demotion", f"{len(new_p)} newly demoted test(s) are the only killers of "
                                                   f"{len(lost)} mutant(s), e.g. {m['mutants'][lost[0]].get('key') or lost[0]}")
        if R["require_unique_kill"] and baseline and baseline.get("id_source") != "matrix":
            info["unique_kill"] = "skipped: baseline test ids come from JUnit, not a matrix (run `tmx.py baseline --matrix`)"
        elif R["require_unique_kill"] and baseline and baseline.get("test_ids"):
            old = set(baseline["test_ids"]) & set(m["tests"])
            new = sorted(set(m["tests"]) - set(baseline["test_ids"]))
            old_kills = {k for k, mu in m["mutants"].items() if set(mu.get("killed_by", [])) & old}
            weak = [t for t in new
                    if not any(t in mu.get("killed_by", []) and k not in old_kills for k, mu in m["mutants"].items())]
            info["new_tests"] = len(new)
            globs = list(policy.get("admission", {}).get("protected", []))
            if globs:
                info["protected_globs"] = "deprecated: a name glob lets any new test opt out by its name; " \
                                          "list exact ids in admission.protected_file"
            exact: Set[str] = set()
            pf = policy.get("admission", {}).get("protected_file")
            if pf:   # exact ids, from the base ref when judging a change (a PR cannot protect itself)
                text = _git(root, "show", f"{base}:{pf}") if base else \
                    (open(os.path.join(root, pf)).read() if os.path.exists(os.path.join(root, pf)) else "")
                exact = {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}
            for t in weak:
                if t not in exact and not _match(t, globs):
                    add("V", "require_unique_kill",
                        f"{t} kills no mutant that the existing suite misses; fold it into an existing "
                        "test/table, or tag it as a protected regression test")

    # Article XI - quarantine age (R5: any quarantined test blocks)
    if head_q and R["quarantine_days"] is not None:
        today = dt.date.today()
        for e in head_q:
            since = dt.date.fromisoformat(e["since"])
            if since > today:
                add("XI", "quarantine_date", f"{e['test']} has a future quarantine date {e['since']}")
            elif R["quarantine_blocks"]:
                add("XI", "quarantine_blocks", f"{R['level']}: {e['test']} is quarantined; nothing ships until it is fixed")
            elif (today - since).days > R["quarantine_days"]:
                add("XI", "quarantine_days",
                    f"{e['test']} quarantined since {e['since']} (> {R['quarantine_days']} days): fix or delete")

    if new_p and not matrix_path:
        add("XII", "uncertified_demotion", f"{len(new_p)} test(s) newly demoted to probation, and no matrix was "
                                           "given to certify that the PR tier still kills what they kill (--matrix)")
    advisory = R["mode"] == "advisory"
    return {"passed": advisory or not v, "advisory": advisory, "violations": v, "info": info}


def _from_base(root: str, base: str, rel: str) -> Optional[str]:
    try:
        return subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root, capture_output=True, text=True,
                              check=True).stdout
    except Exception:
        return None


def main(a) -> int:
    source = a.policy_source or ("base" if a.base else "head")
    rel = os.path.relpath(os.path.abspath(a.policy), os.path.abspath(a.root))
    if source == "base" and a.base:
        # A change is judged by the rules it is proposed against, so it cannot loosen its own gate.
        # Amendments take effect after they merge (land them before the work that needs the room).
        text = _from_base(a.root, a.base, rel)
        if text is None:
            print(f"gate: {rel} does not exist at {a.base}; judging by the working-tree policy (first adoption)")
            source = "head"
        else:
            policy = mini_toml(text) if not _has_tomllib() else __import__("tomllib").loads(text)
    if source == "head":
        if not os.path.exists(a.policy):
            print(f"no policy at {a.policy}; run the test-constitution skill to create one")
            return 2
        policy = load_policy(a.policy)
    if source == "base" and a.base:
        b = _from_base(a.root, a.base, policy.get("baseline", ".test-baseline.json"))
        policy["_from_base"] = True
        policy["_baseline_text"] = b
    try:
        res = run(policy, root=a.root, junit=a.junit, matrix_path=a.matrix, base=a.base,
                  pr_body=os.environ.get("TMX_PR_BODY", ""))
    except SystemExit as e:
        print(e)
        return 2
    if a.json:
        print(json.dumps(res, indent=1, default=sorted))
    else:
        kind = "warning" if res["advisory"] else "error"
        for x in res["violations"]:
            print(f"::{kind} title=Test constitution Art. {x['article']} ({x['rule']})::{x['message']}"
                  if os.environ.get("GITHUB_ACTIONS") else
                  f"{'WARN' if res['advisory'] else 'FAIL'} Art. {x['article']} {x['rule']}: {x['message']}")
        info = {k: v for k, v in res["info"].items() if k != "changed_test_files"}
        verdict = "PASS" if not res["violations"] else \
            f"ADVISORY ({len(res['violations'])} finding(s), not blocking)" if res["advisory"] else \
            f"{len(res['violations'])} violation(s)"
        print(verdict + " " + json.dumps(info, default=str))
    return 0 if res["passed"] else 1


def write_baseline(root: str, out: str, junit: List[str] = (), matrix_path: Optional[str] = None) -> dict:
    """Record the accepted state the ratchet compares against. Prefer --matrix: its ids line up
    with the matrix used for marginal-value admission (Art. V)."""
    b: dict = {"updated": dt.date.today().isoformat()}
    if junit:
        t = junit_totals(list(junit))
        # The PR-tier run excludes probation and quarantine; record them so growth compares like with like.
        hidden = {e.get("test") for n in (".test-probation.json", ".test-quarantine.json")
                  for e in _load_list(os.path.join(root, n))}
        b.update({"tests": t["tests"], "hidden_tests": len(hidden), "seconds": t["seconds"],
                  "test_ids": sorted(t["ids"]), "id_source": "junit"})
    if matrix_path:
        m = mx.load(matrix_path)
        b.update({"test_ids": sorted(m["tests"]), "id_source": "matrix",
                  "mutation": mx.mutation_score(m), "commit": m.get("commit")})
        b.setdefault("tests", len(m["tests"]))   # a matrix already includes demoted tests
        b.setdefault("hidden_tests", 0)
        b.setdefault("seconds", round(sum(float(x.get("duration", 0)) for x in m["tests"].values()), 3))
    with open(os.path.join(root, out), "w") as f:
        json.dump(b, f, indent=1)
        f.write("\n")
    return b
