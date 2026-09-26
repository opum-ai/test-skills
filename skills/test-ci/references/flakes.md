# Flaky tests: quarantine, not retries

## Why no retries in the PR tier

A retry turns a flaky test into one that is green *most of the time*, and it hides real
races. 84% of pass→fail transitions at Google involved a flaky test *(secondary)*. The
root causes are mostly real concurrency and timing defects: async wait 45%, concurrency
20%, test-order dependence 12% (Luo et al. 2014). DORA: "don't tolerate flaky tests".

## `.test-quarantine.json`

```json
[{"test": "tests/test_inventory.py::test_reserve_concurrent", "since": "2026-09-20",
  "owner": "@alice", "issue": "https://github.com/org/repo/issues/123", "type": "flaky"}]
```

- **Adding an entry:** the test is marked (the hook or a marker reads the file) and runs
  only in nightly.
- **Gate:** at R3 it fails when an entry is older than `quarantine_days` (14 by default,
  7 at R4). At R5 any entry in scope blocks.
- **Leaving quarantine** requires one of:
  - **fixed:** 100 consecutive local passes plus a week of nightly green (GitLab's rule);
  - **deleted:** it was low-value or redundant (check the kill matrix);
  - **rewritten** at a lower level.

## Lifecycle (GitLab and Uber models)

`new → stable → unstable (quarantined) → fixed | deleted`

The owner acknowledges within 48 hours. After the maximum age, the default is deletion
with a warning, not indefinite skipping.

## Common fixes

| Cause | Fix |
|---|---|
| sleep-based waiting | wait on the condition (events, polling with a deadline), or inject a fake clock |
| shared state or order | fresh fixtures; `pytest -p randomly` to expose the dependence |
| real concurrency bug | reproduce it deterministically. That is a *finding*; consider proof-skills `formal-verify` |
| network or time | mock at the boundary; freeze time |
