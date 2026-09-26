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
