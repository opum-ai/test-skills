---
name: test-audit
description: "Use this skill to diagnose the health of a whole existing test suite and its CI, and to report how lean it could be without losing fault detection. It builds a per-test mutation kill matrix, certifies a minimal subset, and flags duplicate, subsumed and zero-signal tests, clone clusters, test smells, flakiness and CI tiering problems. Use it when the concern is the suite as a whole: it's bloated, slow, brittle, untrusted or agent-grown; the user wants to know how many tests they really need; they doubt their coverage or mutation score; or they want it checked against a test constitution. Vague complaints like \"CI takes forever\" count. Do not use it for narrow questions about specific named tests, such as whether one test is flaky or whether a given property test subsumes certain example tests. Also skip it for writing new tests, explaining concepts, or carrying out deletions and consolidation, which belong to test-reduce. This skill only measures and recommends."
---

# test-audit

Agent-grown test suites fail in a recognizable way. Every change adds tests, nothing
removes them, and the suite fills with copies, mocks of internals and assertions that
cannot fail. CI slows and flakes, refactors break hundreds of tests, and the extra
thousand tests catch almost nothing the core hundred would not.

This skill measures that precisely. The deliverable is a report that says:
- how many tests the suite really needs;
- which tests those are, with a **certificate**;
- what each of the others is (a duplicate, subsumed, zero-signal, a clone, or a smell);
- where the suite is *too weak* (surviving mutants in critical code);
- what CI should change.

It does not delete anything. That is `test-reduce`, and it starts from this report.

## The engine: `tmx`

`scripts/tmx.py` is stdlib-only Python 3.9+. Siblings reach it at
`${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py`. Set `T=${CLAUDE_SKILL_DIR}/scripts/tmx.py`.

| Command | What it gives you |
|---|---|
| `collect-pytest --src PKG --tests tests -o .tmx/matrix.json` | Per-test coverage, then a **kill matrix**: every mutant of PKG, run against only the tests that cover its line, in throwaway copies. Run it with the project's interpreter (pytest + coverage). |
| `faults faults.json --cmd "<test cmd writing {junit}>" [--matrix m.json]` | Domain faults for **any language**: text patches applied in throwaway copies, run with any JUnit-writing command, merged into the matrix with exact attribution (a fault that breaks compilation is an `error`, never a kill). |
| `import-stryker mutation.json -o .tmx/matrix.json` | The same matrix for JS/TS/C#/Scala from Stryker (`coverageAnalysis: "perTest"`, json reporter). |
| `score .tmx/matrix.json --survivors` | Mutation score, zero-kill tests, surviving mutants. |
| `analyze .tmx/matrix.json -o .tmx/plan.json [--csv keep.csv]` | Smallest subset preserving **every** kill (weighted set cover), reasons per removed test, trade-off curve, certificate; `--csv` writes the per-test keep/remove table for the user. |
| `verify .tmx/plan.json .tmx/matrix.json [--rerun]` | Independent check of the certificate (exit 3 if invalid). `--rerun` also replays every obligation's mutant against the retained suite alone. Use it for any plan that will be acted on. |
| `smells tests/ --src PKG -o .tmx/smells.json` | Static smells, each tagged with the constitution article it breaks. |
| `clones tests/ -o .tmx/clones.json` | Structurally identical tests: parametrize or property candidates, with their literal rows. |
| `gate --policy test-policy.toml ...` | The constitution's machine checks (see `test-ci`). |

For other languages without Stryker, see `references/languages.md`. The fallback is
static smells/clones plus JUnit counts, which gives a partial audit, labelled as such.

## Workflow

1. **Orient (2 minutes).** Find the test runner, the test roots, the source roots, the CI
   config, and whether `TEST-CONSTITUTION.md` / `test-policy.toml` exist. Run the suite
   once with a JUnit report, and record count, wall time and skips. It must be green: a
   kill matrix needs a passing baseline. If it is red, stop and report the failures.
2. **Static pass (cheap, always).** Run `smells` and `clones`, and read the top clusters.
   These findings stand on their own even if mutation is too slow.
3. **Kill matrix (the core evidence).** Run the matrix collector. Budget it before running:
   roughly `mutants × (pytest startup + covering tests' time) / jobs`. For big suites:
   - **Cheap first pass:** `--operators extreme` (one mutant per function) finds
     pseudo-tested functions and zero-signal tests fast.
   - **Sampling:** `--per-line 1` puts at most one mutant on each line, the way Google
     does it at scale.
   - **Real faults:** `--history 20` adds up to 20 *real* faults by reverting past fix
     commits that still apply (see ADR-0002). Always include these when the repo has
     git history.
   - **Scope:** restrict `--src` to one package at a time when the suite is huge. Say so
     in the report.
   - **Domain faults for critical code:** `--extra-mutants faults.json` (pytest collector), or
     `tmx faults faults.json --cmd ...` for any language (for example Vitest with
     `--reporter=junit --outputFile={junit}`, merged into an imported Stryker matrix). Each takes a list of
     `{"file", "find", "replace", "desc"}` entries. The operators cover comparisons,
     arithmetic (including `//` vs `/`), constants up and down, numeric strings,
     `raise` deletion, `min`/`max`/`sum`/`any`/`all` swaps and rounding modes. They do not
     know your domain.

     In the benchmark, a plan certified on operators alone would have let 12 hand-written
     money faults through (a wrong regional tax rate, compounding order, sum vs max). For
     R4 and R5 tiers, write the plausible domain faults (the rate table, the order of
     rules, the rounding boundary) before trusting a reduction.
4. **Analyze and verify.** Run `analyze`, then `verify --rerun`. Add `--lines` if the team also
   wants coverage preserved (it costs slightly more tests). Protect tests the constitution
   marks protected (the exact ids in `testing/protected.txt`, such as regressions for real bugs) with one `--keep <id>` each.
   Then read `plan.json`:
   - `remove` reasons: `zero-signal` (kills nothing), `duplicate`, `subsumed` (by one
     retained test), and `jointly-covered`.
   - `curve`: how few tests reach 80, 90 and 95% of the kills.
   - `optimal` / `lower_bound`: whether the subset is provably minimal for this matrix.
5. **Weakness pass.** Run `score --survivors`. Surviving mutants in critical code are
   *missing* tests. Triage the top ones:
   - an **equivalent mutant** (no behavior change, e.g. `x < lo` → `x <= lo` inside a
     clamp that returns `lo`);
   - a **real gap**: name the missing assertion.
   A lean suite that misses real faults is not the goal.
6. **CI review.** Read the workflow files against `references/ci-review.md`:
   - tiers (PR vs nightly), selection, sharding, caching;
   - retries-to-green, which hide flakes (Article XI);
   - timeouts, and whether the gate is present.
7. **Rigor.** Resolve each path's level from the policy (default R3 when there is none).
   Judge the evidence against that level's obligations
   (`../test-constitution/references/rigor-profiles.md`):
   - R4 paths need every survivor triaged;
   - R5 paths need history mutants killed, traceability and an assurance plan.
   Report **per path and per level**. A critical path audited against R3 thresholds is a
   finding.
8. **Constitution compliance.** If the project has a constitution, check each article and
   mark it pass / fail / not measurable, with evidence. If it has none, report against the
   default articles in `../test-constitution/assets/TEST-CONSTITUTION.md` and recommend
   adopting them.
9. **Write `.tmx/findings.json` and publish the report** (`references/report.md`). Offer
   the next steps:
   - `test-reduce` to apply the plan;
   - `test-constitution` if there is no constitution;
   - `test-ci` for the pipeline;
   - `coverage-proof` where a property or model could replace a cluster.

## Reading the numbers honestly

- A certificate preserves kills *of this mutant set*. State the operators, sampling, files
  and history depth in every summary. Real regressions exist that no mutant models
  (Just et al. found 17% of real faults coupled to no classic mutant), which is why
  `test-reduce` demotes to probation before deleting.
- "Zero-signal" means the test kills no mutant **in the measured scope**. A test of code
  outside `--src`, such as a config file or a template, can look zero-signal while doing
  real work. Check what it touches before calling it dead.
- Timeouts and collection errors count as kills only in the ways `score` shows. Never round
  them up.
- Mutation score is a floor of test strength, not a probability of correctness. Report it
  per risk tier, not as one number.

## What not to do

- Don't propose deleting tests on coverage alone. Coverage-based reduction lost up to 20%
  of mutant kills in the literature. Kill sets are the criterion.
- Don't run mutation on the whole monorepo blind. Estimate first, then sample or scope.
- Don't edit tests or source during an audit. The report is the output.
- Don't report a smell as a verdict. `mock-heavy` in an adapter test at a network boundary
  is correct. The smell list is for review.

## Reference files

- `references/report.md`: the findings.json shape and the report contract (verdict strip,
  reduction projection, weakness list, CI findings, compliance table, re-run commands).
- `references/ci-review.md`: the CI checklist with the sources behind each item.
- `references/languages.md`: matrices for JS/TS (Stryker), Java (PIT), Rust (cargo-mutants),
  Go, and JUnit-only audits.
- `references/interpreting.md`: equivalent-mutant triage, pseudo-tested functions, zero-kill
  tests that still matter, and history mutants.
