"""Generate `claude plugin eval` cases from triggers.py and evals.json. Do not edit cases/ by hand.

    python3 evals/make_cases.py        # rewrites evals/cases/

trigger/<skill>/<nn>-pos|neg : one query; graded by whether the Skill tool loaded the skill.
task/<name>                  : the four benchmark tasks; LLM graders on the final message.
The objective graders (evals/grade.py) are run separately on kept workspaces.
"""
import json
import pathlib
import re
import shutil

from triggers import SETS

HERE = pathlib.Path(__file__).resolve().parent
SKILLS = list(SETS)


def write(p, text, mode=None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if mode:
        p.chmod(mode)


def yq(s):
    return "'" + s.replace("'", "''") + "'"


def skill_re(name):
    return r'"skill"\s*:\s*"(?:[\w-]+:)?' + name + '"'


def tool_grader(name, weight, positive, note):
    bounds = "" if positive else "min: 0\nmax: 0\n"
    return f"---\ntype: tool_used\ntool: Skill\ninput_match: {yq(skill_re(name))}\n{bounds}weight: {weight}\n---\n\n{note}\n"


SCAFFOLD = """#!/usr/bin/env bash
set -euo pipefail
FIX="$(cd "$(dirname "$0")/../../../../fixtures/py-bloated-shop" && pwd)"
cp -R "$FIX"/. .
"""


def main():
    out = HERE / "cases"
    if out.exists():
        shutil.rmtree(out)
    n = 0
    for skill, items in SETS.items():
        for i, (q, pos) in enumerate(items, 1):
            d = out / "trigger" / skill / f"{i:02d}-{'pos' if pos else 'neg'}"
            write(d / "case.yaml", f'schema_version: "1.1"\nname: trigger-{skill}-{i:02d}\ncontext:\n  scaffold_script: scaffold.sh\n')
            write(d / "prompt.md", "---\n" + f"description: {yq(('Should trigger ' if pos else 'Near miss: should NOT trigger ') + skill)}\n"
                  f"tags: [trigger, {skill}, {'positive' if pos else 'negative'}]\nruns: 1\nmax_turns: 6\ntimeout_seconds: 150\n"
                  "allowed_tools: [Read, Glob, Grep, Skill]\n---\n\n" + q + "\n")
            write(d / "scaffold.sh", SCAFFOLD, 0o755)
            if pos:
                write(d / "graders" / f"fired-{skill}.md", tool_grader(skill, 2, True, f"The {skill} skill was loaded."))
                write(d / "graders" / "fired-any.md", tool_grader("(?:" + "|".join(SKILLS) + ")", 1, True, "Some test-skills skill was loaded."))
            else:
                write(d / "graders" / f"not-fired-{skill}.md", tool_grader(skill, 1, False, f"The {skill} skill was NOT loaded."))
            n += 1
    evals = json.loads((HERE / "evals.json").read_text())["evals"]
    # plugin eval's graders read only what the agent produced; they cannot run grade.py. Assertions
    # that cite grader-held evidence become checks on what the report claims, and grade.py re-checks
    # the truth on the kept workspaces afterwards (evals/grade_plugin_eval.py). None = objective only.
    JUDGE = {
        "No fault detection was lost: the grader-held mutant set shows zero lost kills (objective lost_kill_count == 0), "
        "and the agent produced its own before/after comparison or certificate":
            "No fault detection was lost: the report shows a before/after mutation comparison or certificate with zero lost kills",
        "The implementation passes the hidden acceptance tests (graded objectively)": None,
        # A judge cannot see file changes from the report; grade.py compares tree hashes with a pristine copy.
        "Did not modify tests/ or shop/": None,
        "Did not modify the shop/ source code": None,
        "Did not modify src/ or test/": None,
        "The new tests achieve a mutation score of at least 85% on the new loyalty code (objective mutation_new_code.score)":
            "The report gives a measured mutation score of at least 85% on the new loyalty code",
        "At most 36 test cases added (parametrized rows count; objective tests_added). 36 is 1.5x the 21-24 case minimal "
        "fault-equivalent sets the iteration-1 runs measured":
            "The report states how many test cases were added (parametrized rows count), and it is at most 36",
        "The new tests have no test smells (objective smells is empty)":
            "The report says the new tests were checked for test smells (no-assertion, tautology, sleeps, private-state "
            "asserts) and none remain",
    }
    for e in evals:
        d = out / "task" / e["name"]
        write(d / "case.yaml", f'schema_version: "1.1"\nname: task-{e["name"]}\ncontext:\n  scaffold_script: scaffold.sh\n')
        write(d / "prompt.md", "---\n" + f"description: {yq(e['name'])}\ntags: [task, {e['expected_skill']}]\nruns: 1\nmax_turns: 200\n"
              "timeout_seconds: 3600\nallowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]\n---\n\n" + e["prompt"] + "\n")
        write(d / "scaffold.sh", SCAFFOLD.replace("py-bloated-shop", e["fixture"]).replace("../../../../", "../../../")
              + '[ -x ./make_history.sh ] && ./make_history.sh >/dev/null || (git init -q && git add -A && git -c user.email=e@e -c user.name=e commit -qm init)\n'
              + '"$(dirname "$0")/../../../stage_toolchain.sh"   # python/git/npx that work inside the eval sandbox\n'
              + ('node "$(dirname "$0")/../../../sandbox_patch_stryker.cjs"   # Stryker without a TCP log server\n'
                 if e["fixture"].startswith("ts-") else ""), 0o755)
        for i, a in enumerate(e["assertions"], 1):
            if re.search(r"objective|grader-held|hidden", a) and a not in JUDGE:
                raise SystemExit(f"{e['name']} #{i} cites grader-only evidence; add a JUDGE rewrite: {a}")
            a = JUDGE.get(a, a)
            if a is None:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-")[:48].rstrip("-")
            write(d / "graders" / f"a{i:02d}-{slug}.md", "---\ntype: llm\nfocus: last_message\n---\n\n"
                  "PASS if the agent's final report states or shows the following with specifics (names, numbers, "
                  f"files or commands):\n\n{a}\n\nFAIL if absent, vague, or contradicted.\n")
        write(d / "graders" / f"z-fired-{e['expected_skill']}.md", tool_grader(e["expected_skill"], 1, True, "with-arm indicator"))
    print(f"wrote {n} trigger cases and {len(evals)} task cases under {out}")


if __name__ == "__main__":
    main()
