---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: "Demote before delete: probation tier for removed tests"
tags:
  - architecture
summary: "Tests a certified plan removes are first moved to a probation tier that runs nightly; they are deleted only after a probation window in which none of them uniquely failed."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.055Z
---

# Demote before delete: probation tier for removed tests

## Status

Accepted (2026-09-26)

## Context

A kill-set certificate is necessary but not sufficient. Replaying 1,478 real failed Travis
builds, Shi et al. (ISSTA 2018) found that reduced suites missed up to 52.2% of failed builds,
although traditional metrics showed only 2–3% mutant or coverage loss. The same study found
that an oracle could have kept about 20% of tests and missed nothing, so the redundancy is
real but hard to identify ahead of time.

Google TAP and Meta Predictive Test Selection both separate *running less often* (safe and
reversible) from *deleting* (irreversible). Deleting tests is also the classic way agents
fake a green build, which is why practitioners argue that test deletion should be a
privileged, separately reviewed change.

## Decision

`test-reduce` works in three stages:
1. **Consolidate.** Merge clones into parametrized tests or properties. No signal is lost,
   and the reduction is re-verified.
2. **Demote.** Move certified-redundant tests to a probation tier: a `probation` marker or
   directory, excluded from the PR tier and run nightly.
3. **Delete.** After the probation window (default 14 days or 20 nightly runs, set in
   policy), delete the demoted tests that never failed uniquely. A demoted test that
   catches a regression the retained suite missed is promoted back, and its case is
   recorded as a new mutant or history obligation.

Deletion is always its own reviewable change. It carries the certificate and the probation
log, and it is never mixed with feature work.

## Consequences

- The PR tier gets the full speed benefit immediately. Deletion lags by one probation window.
- Nightly cost falls only after deletion, which is acceptable because nightly is not on the
  developer's critical path.
- Teams in a hurry can shorten the window in `test-policy.toml`, and the report says so.
