# Choosing the numbers

| Setting | Default | How to choose | Amend when |
|---|---|---|---|
| `rigor` | R3 | Use the decision questions in rigor-profiles.md. Set per tier, not globally high. | The product's risk changes, for example it starts handling money. |
| `max_tests` | today's count (adoption), then the certified minimum × 1.3–1.5 after the first reduction | Headroom for real growth; less means more trailers | New modules genuinely need room. Say which. |
| `max_suite_seconds` | 300 | PR tier ≤ 10 min end to end (DORA, Fowler); the test step about half of that | Never, just because tests got slow. Move them to nightly instead. |
| `max_new_tests_per_pr` | 8 | About the size of one well-planned feature (a few tables and properties) | Rarely. Prefer the trailer for exceptions. |
| tier `min_mutation_score` | critical 0.80, standard 0.60 | Stryker's high/low defaults (80/60); Google's findings rate; raise for money or auth | After measuring. Never set it above the current score on adoption day; ratchet up. |
| `forbid_smells` | no-assertion, tautology, swallowed-exception, sleep, skipped | Add `implementation-coupled` once the suite is clean | — |
| `max_mocks_per_test` | 3 (R4: 2) | Adapters at I/O boundaries may need more. Put those in a path-specific exception. | — |
| `quarantine_days` | 14 (R4: 7) | GitLab's fast quarantine is ≤ 3 days, long ≤ 3 months | — |
| `probation.days` / `min_nightly_runs` | 14 / 20 | Long enough for about 20 nightly runs across typical churn | A team that runs nightly twice a day can halve the days. |

A reason to amend names a real cost ("PR tier now 11 min because the new e2e suite covers
payments; moving it to nightly isn't acceptable because…"). "The gate fails" is never a
reason by itself.
