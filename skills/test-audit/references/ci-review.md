# CI review checklist

Read every workflow file (`.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`,
`buildkite`, `circleci`). Each item names the constitution article it relates to and a source.

| # | Check | Good | Smell | Article / source |
|---|---|---|---|---|
| 1 | PR tier wall time | ≤ 10 min end to end; the test step fits `max_suite_seconds` | the full suite plus e2e on every push | II, X; Fowler's ten-minute build; Google presubmit ~11 min |
| 2 | Tiers | PR = fast and hermetic; nightly = slow, probation, mutation | one job runs everything | X; Google TAP presubmit/post-submit split |
| 3 | Retries | none in the PR tier; flakes are quarantined | `--reruns`, retry loops, `retry: 2` | XI; Google: 84% of pass→fail transitions involve flaky tests |
| 4 | Quarantine | a file with dates; the gate fails on stale entries | `@skip("flaky")` forever | XI; Fowler: cap the quarantine size and age |
| 5 | Selection | affected-test selection or per-path jobs on large repos | every test for a README change | Yoo & Harman; Nx/Bazel affected; Meta PTS |
| 6 | Sharding / parallelism | `pytest -n`, `--shard`, matrix jobs once > 5 min | serial suite | Bazel `TEST_TOTAL_SHARDS`; Linear 2026 |
| 7 | Caching | dependency and build cache | reinstalls every run | — |
| 8 | Gate | `tmx gate` runs, with a baseline and policy | no budget enforcement | II–VI, XI; ADR-0004 |
| 9 | Mutation | on the diff for PRs, full nightly | none, or full mutation on every PR | III; Google diff-based mutation |
| 10 | Timeouts | per-test and per-job timeouts | hung jobs block the queue | X; Bazel timeouts by size |
| 11 | Coverage gate | per-tier, diagnostic, or mutation-based | a global "coverage ≥ 90%" gate | III; Inozemtseva & Holmes; Google 60/75/90 |
| 12 | Test result reporting | JUnit artifact uploaded (the gate's input) | logs only | — |

Report each failed item as a CI finding: severity, `file:line`, and a recommendation. The
`test-ci` skill implements the recommendations.
