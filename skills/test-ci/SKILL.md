---
name: test-ci
description: Design or fix a CI test pipeline that stays fast and trustworthy as the suite and the agent-driven change rate grow - PR vs nightly tiers under a time budget, affected-test selection, sharding, flake quarantine with an expiry, no retry-until-green, the test-constitution gate with a budget ratchet, diff-scoped mutation testing on PRs and full mutation nightly, probation runs, and rigor-level approvals. Use this skill whenever the user asks to speed up CI, restructure test jobs, add or fix a test gate, handle flaky tests, add mutation testing to CI, enforce test budgets or a test policy in GitHub Actions/GitLab/other CI, or says CI is slow, red for no reason, or can't keep up with agent PRs.
---

# test-ci

When agents raise the change rate, CI becomes the bottleneck. The usual responses (bigger
runners, retries, `@skip("flaky")`) make CI slower, less trusted, or both. The DORA
research is blunt: feedback within about 10 minutes, no tolerance for flaky tests, and "ten
tests that are reliable, fast, and trustworthy" over hundreds nobody trusts.

This skill builds a pipeline in which:
- the PR tier stays inside its budget;
- the slow and uncertain parts move to tiers that don't block developers;
- the test constitution is enforced by a machine.

`T=${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py`. Templates are in `assets/`.

## Target shape

| Tier | Trigger | Budget | Runs | Blocks merge? |
|---|---|---|---|---|
| **PR** | every PR push | ≤ `max_suite_seconds`; the whole job ≤ 10 min | fast hermetic tests, excluding `probation` and `slow`; affected-only on large repos; `tmx gate --base`; mutation on the diff for R4+ paths | yes |
| **Merge / main** | push to main | ≤ 20 min | the full non-probation suite (a safety net for selection); refresh the baseline | yes (revert on red) |
| **Nightly** | schedule | ≤ 60 min, sharded | everything, including probation, plus `probation record`; full kill matrix (sampled); `tmx gate --matrix` | no; opens an issue |
| **Release** (R5 paths) | tag | as needed | full mutation, the evidence bundle, approvals | yes |

## Workflow

1. **Read the current pipeline** against `../test-audit/references/ci-review.md`, and
   record the numbers: PR-tier wall time, test step time, retries, skips, quarantine,
   selection, sharding, caching. If an audit exists, use its CI findings.
2. **Read the policy.** Take the budgets, tiers, probation settings and the rigor of each
   path from `test-policy.toml`. If there is no policy, recommend `test-constitution` first.
   You can still restructure tiers without it.
3. **Restructure into tiers.**
   - **Split by size.** Mark slow or large tests (`@pytest.mark.slow`, tags, or a
     directory) and move them to nightly.
   - **Selection.** For large repos, add affected-test selection (Nx, Bazel, pytest-testmon,
     or path filters per package). Always keep the full run on main as the safety net
     (Shopify, Google TAP).
   - **Parallelism.** Shard when the PR test step takes more than about 5 minutes
     (`pytest -n auto`, a job matrix with `--shard`, `TEST_TOTAL_SHARDS`). Cache
     dependencies.
4. **Flakes** (Article XI; `references/flakes.md`).
   - Remove retry-until-green from the PR tier. Replace it with a **quarantine**:
     `.test-quarantine.json` lists the test, since-date, owner and issue.
   - The quarantined test runs only in nightly. The gate fails once an entry outlives
     `quarantine_days`, which is 7 at R4 and 14 at R3. At R5 any quarantined test blocks.
   - GitLab's lifecycle is a good model: fast quarantine ≤ 3 days, long ≤ 3 months, then
     automatic deletion.
5. **Wire the gate** (`assets/github-actions.yml`, `assets/gitlab-ci.yml`).
   - The PR job runs the tests with JUnit output, then:
     `python3 tmx.py gate --policy test-policy.toml --junit report.xml --base origin/$BASE`.
   - The gate reads `test-policy.toml` and `.test-baseline.json` **from the base ref** by
     default whenever `--base` is given. A PR that edits them is still judged by the old
     rules. `--policy-source head` exists only for first adoption.
   - Vendor `tmx` into the repo (`tools/tmx/`) or pin the plugin path. CI must not depend
     on the plugin being installed.
   - **Pass the PR body** as `TMX_PR_BODY` so the `Test-Budget:` and `Rigor:` trailers are
     seen.
   - **For R4/R5, pass approvals from the platform's review record** as
     `TMX_PR_APPROVERS`, for example
     `gh pr view --json reviews -q '[.reviews[] | select(.state=="APPROVED") | .author.login] | join(",")'`.
     Never pass them from anything the PR author controls.
   - Also add the approvers as required reviewers or CODEOWNERS, so the platform enforces
     them too.
6. **Mutation in CI.**
   - **PRs:** diff-scoped. Run `collect-pytest --src <changed modules> --per-line 1`, or
     Stryker `--incremental` / `--since`, or cargo-mutants `--in-diff`. Then
     `gate --matrix`.
   - **Nightly:** the full matrix, sampled and sharded, and `baseline --matrix` so the next
     day's marginal-value checks have ids.
   Keep PR mutation inside the tier budget. If it cannot fit, run it only for R4+ paths.
7. **Probation** (ADR-0003). Nightly runs `pytest` with no marker filter and JUnit output,
   then `$T probation record --junit nightly.xml`. If any probation test failed, it opens an
   issue: that is a regression the retained suite missed. A weekly job runs
   `probation prune --days … --min-runs …` on a branch and opens the deletion PR, which is
   never auto-merged.
8. **Verify on a real run.**
   - Push the branch and watch the PR job. Report the measured PR-tier time, not an
     estimate.
   - Confirm the gate fails when it should. Push a throwaway commit with a no-assertion
     test on a scratch branch, see it red, then drop it. A gate that has never failed is
     not known to work.
   - Say "no checks configured" if the repo has none, rather than implying green.
9. **Report.**
   - A before/after table: PR wall time, tests in the PR tier, retries, quarantine size,
     gates.
   - Which article each job enforces, and at what rigor.
   - The exact workflow diff.

## Rigor in CI

| Level | CI obligations |
|---|---|
| R1 | none required; if a gate runs, it runs in advisory mode |
| R2 | a PR tier with the gate; smells and budget |
| R3 | PR + nightly; the full default gate; nightly mutation and probation |
| R4 | + mutation on the diff in the PR tier; waivers need platform approval; quarantine ≤ 7 days |
| R5 | + release tier with full mutation and an archived evidence bundle; `TMX_PR_APPROVERS` from the review record is required; zero quarantine |

## Reference files

- `assets/github-actions.yml`: a PR, main and nightly workflow with the gate, probation and
  mutation.
- `assets/gitlab-ci.yml`: the same, for GitLab.
- `references/flakes.md`: the quarantine file format, the lifecycle, the owner rule, and
  root causes (async wait 45%, concurrency 20%, order dependence 12%).
- `references/selection.md`: affected-test selection by ecosystem, with the safety nets
  that keep it honest.
