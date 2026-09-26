---
name: test-reduce
description: Radically shrink an existing test suite without losing fault detection - consolidate copy-paste tests into parametrized tables and properties, demote certified-redundant tests to a nightly probation tier, delete them after probation, and prove at every step (mutation kill-set certificate, before/after matrix compare) that nothing the suite used to catch is lost. Use this skill whenever the user wants to cut, prune, slim, deduplicate, consolidate or clean up tests, get a bloated suite (hundreds or thousands of agent-written tests) back under budget, bring a project into compliance with its test constitution, or act on a test-audit report - including "delete the useless tests", "we have 3000 tests and CI takes 40 minutes", or "make the suite maintainable again". Starts with test-audit if no current audit exists.
---

# test-reduce

Deleting tests is easy. Deleting tests *safely* is the job. Every reduction here is backed
by evidence a reviewer can check, and it moves in reversible stages:

**consolidate → demote → delete**

Each stage ends with a re-measurement showing that no killed mutant (and no history mutant,
meaning a real past bug) went uncaught.

The ordering follows the evidence. Kill-set-preserving reduction loses nothing *measurable*
(Shi et al. 2014), but real regressions have slipped past reduced suites (up to 52% of
failed builds in Shi et al. 2018). Tests therefore spend a probation window in the nightly
tier before they are deleted (ADR-0003).

`T=${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py`.

## Preconditions

- There is a current audit: `.tmx/matrix.json` and `.tmx/plan.json` from `test-audit`, at
  **this commit**, and `tmx.py verify --rerun` passes.
  - The rerun replays each mutant against the retained suite alone. It catches kills that
    only happened because of test order or shared state.
  - For money, auth and other critical code, the matrix includes domain faults
    (`--extra-mutants`). Operators alone are not enough there. If not, run `test-audit` first; at minimum
  run steps 1 and 3–4 of its workflow.
- The suite is green and the working tree is clean.
- The work is on its own branch. The reduction ships as **its own change**, never mixed
  with feature work (Article XII).
- Honor the user's constraints. If they said "don't delete anything yet", stop after
  demotion. If they gave a target such as "under 300 tests" or "CI under 5 minutes", use
  the plan's `curve` to show whether the certified cut reaches it. Never cross it by
  dropping kills without their explicit OK.

## Rigor limits how hard to cut

Resolve each path's level from the policy (see
`../test-constitution/references/rigor-profiles.md`). Honor the strictest level the tests
touch, meaning the source they cover:

| Level | Reduction rules |
|---|---|
| R1–R2 | Certificate over kills; probation of 0–3 days. At R1 the tests may simply be deleted, since nothing is kept. |
| R3 | Certificate over kills plus history mutants; probation of 14 days / 20 runs. |
| R4 | Certificate over kills **and lines** (`analyze --lines`); history mutants required; probation of 30 days / 30 runs; a human reviews the deletion PR. |
| R5 | Only with an assurance-case update showing that every requirement and hazard keeps its verification. Tests traced to requirements are `--keep`-protected unless the claim moves that requirement to another test. An independent approval is required. The agent prepares the change; it never merges it. |

## Workflow

### 1. Consolidate: fewer tests, same signal

Start from the clone clusters (`.tmx/clones.json`) and the `duplicate` / `subsumed`
groups in the plan. For each cluster, pick one form:
- **A parametrized table.** Use it when the rows are the equivalence classes and
  boundaries of one behavior. One row per class or boundary, *not* per example. Drop
  rows that fall in the same class as another row, unless the code branches between them
  (Article VII).
- **A property.** Use it when the rows follow a rule you can state, for example "total is
  never negative", "round-trip parse(format(x)) == x", or "discount is monotone in
  spend". Use Hypothesis, fast-check, proptest or jqwik, whichever is already in the
  project. The expected value must come from the spec, not from calling the code under
  test (Article IV). See `references/consolidation.md` for patterns.
- **A merge into the strongest existing test.** Use it when the others are weaker copies,
  for example the same call with fewer assertions.

Rewrite behavior-coupled tests while you are there:
- a mock of an internal helper becomes a real call;
- an assertion on private state becomes an assertion on the public result;
- a call-order assertion becomes an assertion on the outcome (Article VI).

Delete tautologies and no-assertion tests outright. They are provably zero-signal
(Article IV), so no probation is needed. Say so in the log.

After each batch, **re-measure and compare**:
```bash
$T collect-pytest --src PKG --tests tests -o .tmx/after.json [same flags as the audit]
$T compare .tmx/matrix.json .tmx/after.json      # exit 3 = something is no longer killed
```
If anything is lost, the consolidation dropped a behavior. Restore the row or assertion
that killed it. Never "fix" this by weakening the mutant set.

### 2. Demote: out of the PR tier, into probation

Re-run `analyze` on the consolidated matrix, then `verify`. Demote what it removes:
```bash
$T analyze .tmx/after.json -o .tmx/plan2.json $(sed 's/^/--keep /' testing/protected.txt)   # exact protected ids
$T verify .tmx/plan2.json .tmx/after.json --rerun   # empirical: the retained suite alone catches each one
$T probation add --plan .tmx/plan2.json          # writes .test-probation.json (refuses uncovered/empty plans)
$T probation install --conftest conftest.py      # pytest hook; marks listed tests `probation`
```
- **PR tier:** `pytest -m "not probation"`. Speed improves immediately.
- **Nightly:** runs everything, then `$T probation record --junit nightly.xml`.
- **A failing probation test is promoted back** by removing it from the list. Its failure
  is a regression the retained suite missed. Add that case as a retained test or a
  history mutant, and note it in the report.

For JS/TS and other runners, follow `references/probation-other-runners.md`: a
tag/grep-based exclusion from the same list.

### 3. Delete: after the probation window

```bash
$T probation status --days 14 --min-runs 20
$T probation prune --days 14 --min-runs 20       # removes whole test functions via AST
```
Use the window from `test-policy.toml` `[probation]`. Shorten it only if the user
explicitly accepts the risk, and record that in the report. `prune` deletes only whole
functions. A parametrized function with some cases due is reported under
`partial_tables`; edit those rows by hand.

### 4. Re-verify, ratchet, report

- Run the full suite (green), then re-collect the matrix and `compare` it against the
  **original** audit matrix. That compare is the end-to-end evidence: zero lost
  obligations.
- Ratchet the budget:
  - write the new baseline: `$T baseline --matrix .tmx/final.json --junit junit.xml`;
  - lower `max_tests` in `test-policy.toml` to the new count plus headroom, as an
    amendment with its reason.
- Update `.tmx/findings.json` (`kind: "reduction"`) and publish the report
  (`references/report.md`):
  - tests and seconds, before and after;
  - what was consolidated, into what;
  - demoted and deleted counts, with reasons;
  - the compare log;
  - survivors, which are unchanged or better;
  - the probation schedule.
- Commit in reviewable slices. Each commit message names the evidence:
  - `test: consolidate 14 coupon-expiry tests into 1 table (compare: 0 lost)`
  - `test: demote 96 certified-redundant tests to probation (plan2 verify: VALID)`
  - `test: delete 96 tests after 14-day probation (0 failures in 20 nightly runs)`

## Honesty rules

- Say what the certificate covers: the mutant operators, sampling, files and history depth.
- Never delete a test to make CI green. A red suite is fixed first, in a separate change.
- Never weaken the mutant set, the `--lines` choice or the protected list between the
  audit and the final compare. Changing any of them resets the comparison, and the report
  must say so.
- If a consolidation *adds* kills (`newly_killed > 0`), report it. It usually means an
  assertion got stronger, which is a good outcome worth showing.

## Reference files

- `references/consolidation.md`: table vs property vs merge, with before/after examples
  in pytest, Hypothesis, Jest/Vitest and fast-check, plus the oracle rules.
- `references/probation-other-runners.md`: probation lists for Jest, Vitest, Go, Cargo
  and JUnit5.
- `references/report.md`: the reduction report contract.
