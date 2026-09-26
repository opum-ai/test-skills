---
type: Arc
title: Skill evaluation suite
tags:
  - skills
summary: With/without-skill benchmark on four fixtures, graded objectively (re-collected kill matrices, hidden acceptance tests) and by assertions.
tasks:
  - ts-10
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:34.096Z
lore_task_status: done
---

# Skill evaluation suite

## Goal

Show whether the skills change outcomes, measured by graders that never trust the agent's own claims.

## Acceptance criteria

- Graders validated on control workspaces
- Results recorded here with the per-case numbers

## Tasks

<!-- lore:tasks:begin -->
| Task | Title | Status |
|---|---|---|
| [TS-10](../../.quest/completed/TS-10.json) | Skill evaluation suite | Done |
<!-- lore:tasks:end -->

## Notes

### Results: 2026-09-26, claude-opus-5-5, one run per arm

**Method.**
- **Arms.** Four task cases; each run once with the skills and once without. Both arms got the
  same prompt and the same pinned Python. Baseline agents were confined to their workspace.
- **Objective grading** with `evals/grade.py`. For `shop-reduce` it:
  - grafts the agent's tests onto a pristine copy of the fixture history;
  - re-collects the kill matrix on the PR tier, with an **expanded operator set that neither
    agent used**;
  - counts lost kills and the three real historical bugs.
  For `loyalty-greenfield` it runs 43 hidden acceptance tests.
- **Blind assertion grading.** Workspaces were copied to A/B under a random mapping, and each
  grader verified claims against the files rather than trusting the final message.
- **Blinding is imperfect.** The with-skill transcripts mention the engine by name.

| Case | Blind score, with | Blind score, without | Assertions with / without | Key objective numbers (with vs without) |
|---|---|---|---|---|
| shop-audit | 8 | **9** | 10/10 · 10/10 | Certified optimal minimum 30 (lower bound 30), verify VALID, vs exact-search minimum 39 with the reduced suite re-run. Both left tests and source untouched. |
| shop-reduce | **8** | 6.5 | 8/8 · 7/8 | PR tier **44** (+13 on probation) vs 79. **0 lost** of 274 kills in both, under the expanded operators. 3/3 history bugs in both. |
| loyalty-greenfield | **8** | 7 | 6/7 · 6/7 | 43/43 hidden tests in both. **33 vs 66** test cases added. Mutation on new code **98.7% vs 95.3%**. 0 vs 2 smells. |
| constitution-setup | **8** | 6 | 8/8 · 6/8 | Both day-one green with no retry loop. Only the with-skill PR gate resisted a PR loosening its own policy, and only it did mutation-based admission and quarantine. |
| **Mean** | **8.0** | 7.1 | **32/33 · 29/33** | |

**Cost.** The with-skill runs took 593–1,782 s and 157–207k tokens. The baselines took
488–1,174 s and 68–138k tokens. The skills cost roughly 1.3–2× more, because they build
evidence the baselines skip: certificates, per-stage compare logs, probation, partition models.

**Trigger suite:** 48/48, one run per case ($13.06). Eleven runs hit `max_turns`. On the
positives the skill fired in the first turns; on the three near misses, the agent worked six
turns without loading the skill. There is no variance data yet.

### What the benchmark changed in the plugin

The evaluation was run to find defects, not to pass. Every item below came from a run or a
grader, was fixed in the same session, and has a regression test.
- **Money blind spot.** The with-skill reduction found that a plan certified on the
  standard operators would have let 12 hand-written money faults through. The mutator now
  covers numeric string literals, rounding modes, `raise` deletion, `min`/`max`/`sum`/
  `any`/`all` swaps, `//` vs `/` and constants down. `--extra-mutants` adds domain faults,
  and critical tiers are told to use it.
- **Re-run the reduced suite.** The audit grader preferred the baseline for re-running its
  reduced suite. `verify --rerun` now replays every obligation's mutant against the
  retained suite alone, and the audit and reduce skills require it.
- **A PR cannot loosen its own gate.** A constitution run judged PRs by `main`'s policy, and
  that is now the gate's default. The grader then found name-glob protection gameable
  (`*regression*`), so protection is now exact ids in `testing/protected.txt`, read from
  the base ref. `adopt.py --codeowners` routes the governance files to a human.
- **Reports.** They lead with the plain answer and keep tool vocabulary in the evidence
  section. `analyze --csv` gives the per-test keep/remove table.
- **Data-only admission.** A new rate row now has a mutant of its own, the numeric literal,
  so it is admitted as a table row.

### Engine review (adversarial, same day)

An independent review found 12 verified defects. The certificate solver itself was sound:
3,000 random instances were fuzzed against brute force. The defects were in what fed it and
in the code around it:
- probation `prune` deleting retained parametrize cases, and mis-slicing on `\x0c`;
- shared-fixture killers missed by coverage attribution;
- order-dependent false kills;
- timeouts and empty matrices certifying deletion;
- colliding mutant keys;
- the gate trusting PR-side state files, and scoping holes;
- rigor floors that explicit policy could loosen;
- smell false positives.

All are fixed. 13 new regression tests **fail on the pre-fix engine and pass after**.

### Results: iteration 1, skill-creator benchmark, 3 runs per arm (2026-09-26)

**Method.** This follows the skill-creator process: 5 cases × with/without skills × 3 runs =
30 agent runs on claude-opus-5-5.
- **Grading.** Each run was graded by `evals/grade.py` (objective, with the grader-held
  mutants and hidden tests) and by a skill-creator grader agent per case. The grader
  verified each assertion against the workspace files and wrote `grading.json` with the
  fields text/passed/evidence.
- **Aggregation.** `aggregate_benchmark` gave mean ± stddev.
- **Review.** A static `generate_review.py` viewer was produced for human review.
- **Cases.** The fifth case, `ts-audit`, is the TypeScript fixture with a real Stryker run
  (TS-13).

| Case | With skills | Without | Discriminating evidence |
|---|---|---|---|
| shop-audit | **13, 13, 13** /13 | 12, 11, 12 | Hand-written domain faults (#12) and reversible staging (#13, 3/3 vs 0/3). |
| shop-reduce | **8, 8, 8** /8 | 5, 7, 7 | PR tier **49/55/57** vs 97/103/109 collected items, all green. Lost kills under the grader's mutants: **0** in all three with-skill runs; one baseline lost the NY tax-rate kill, which its own tool missed. 3/3 history bugs in all six runs. |
| loyalty-greenfield | **6, 6, 6** /7 | 5, 5, 6 | 43/43 hidden acceptance tests in all six runs. **34–41** vs 36–52 cases added. No smells vs at least one per baseline. Spec-derived oracles 3/3 vs 1/3. |
| constitution-setup | **8, 7, 8** /8 | 7, 7, 8 | See the skill defect below. |
| ts-audit | 9, 9, 8 /9 | 9, 9, 8 | No difference: strong baselines also build kill matrices and set covers. |
| **Pass rate** | **96% ± 6%** | 87% ± 11% | +9 points; the skill arm is also less variable |

**Cost.** Tokens were 152k ± 22k vs 111k ± 24k (+36%). Time was 950 s ± 416 s vs 792 s ± 391 s
(+20%). The largest gap is loyalty-greenfield (1.7× tokens), where the skill plans partitions,
generates covering rows and triages survivors.

**What the graders found, and what changed.**
- **Constitution: day-one gate red on money files.** One constitution run left 5 real money
  survivors untriaged. A comment-only PR to `discounts.py` failed its R4 gate, and so did its
  nightly run. `test-constitution` now requires, at R4+, a PR-gate check on a no-op change to
  one file per critical tier, with every real survivor killed or triaged before it finishes.
- **Loyalty: pruning below the plan.** One loyalty run pruned covering-array rows below the
  planned strength, from t=2 to t=1. `test-plan` now says pruning never lowers the plan;
  dropping t is a plan change with a stated reason.
- **Hand-built fault runners.** All four TypeScript runs hand-built a domain-fault runner. That
  is now `tmx faults`: language-agnostic, with a green control run first and kills attributed
  only to tests that passed in the control run.
- **Refactor brittleness.** The baselines measured refactor brittleness by actually refactoring.
  `test-audit` now does the same (step 5).
- **Assertions.** Several did not discriminate: ts-audit overall; constitution #2–#6 and #8;
  loyalty #1, #2, #4, #5 and #7. Loyalty's "≤ 30 cases" failed in all six runs; the runs'
  own minimal fault-equivalent sets were 21–24 cases. `evals/evals.json` now:
  - counts collected PR-tier items;
  - requires zero lost kills on the grader-held mutants;
  - requires an actual revert-and-rerun of the history bugs;
  - splits loyalty's size and score, and adds a no-smells check.
  The ts-audit grader recommends a hidden fault set for the next iteration.
- **Grader tooling.** `grade.py`'s retry-loop detector matched comments that said "no
  retries", so it now reads only executable lines. skill-creator's `aggregate_benchmark` took
  tokens from `grading.json` output_chars whenever a grader filled in timing; it was patched
  locally to read `timing.json`.

The aggregated `benchmark.json`/`benchmark.md` and each skill's `run_loop` result are in
`evals/benchmarks/iteration-1/`.

**Trigger descriptions (`run_loop`).** The loop used a 60/40 train/test holdout and 3 runs per
query, in a stub project root.

| Skill | Held-out test, original → best | Applied |
|---|---|---|
| test-audit | 6/8 → **8/8** | yes |
| coverage-proof | 7/8 → 7/8 (loop); a hand-edited scope sentence scored 20/20 on the full set vs 18/20 | yes (the hand edit) |
| test-reduce | 7/8 → 7/8 (19/20 on the full set; a tie) | no, original kept |
| test-plan, test-constitution, test-ci | 8/8 → 8/8 | no change needed |
