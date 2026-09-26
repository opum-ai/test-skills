# Test Constitution

<!-- Adopted from the test-skills template v0.1. Edit freely; record changes in the Amendment log.
     Numbers live in test-policy.toml; `tmx gate` enforces every article marked [gate]. -->

**Project:** {{project}} · **Adopted:** {{date}} · **Policy:** `test-policy.toml` · **Version:** 1
**Rigor:** project default **{{rigor}}**, critical tier **{{critical_rigor}}** (profiles R1 Minimal · R2 Lightweight ·
R3 Standard · R4 Strict · R5 High-Assurance; a change is held to the highest level of anything it touches)

A test suite is a product with a budget, not a sediment of every change ever made. This
constitution sets the rules *before* the suite grows, so that humans and agents add the
tests that pay for themselves and remove the ones that do not.

## Article I: Purpose and traceability

Every test protects a named behavior that matters: a requirement, a public contract, a
past bug, or a risk in the risk register. Its name or docstring says which. A test that
cannot name what it protects is a candidate for deletion.

## Article II: Budget [gate]

The suite has finite budgets, declared in `test-policy.toml`:
- a maximum test count;
- a wall-time limit for each CI tier;
- a maximum number of new tests per change.

Growth beyond the per-change limit needs a `Test-Budget: <reason>` trailer, and growth beyond
the total budget needs an amendment. The baseline (`.test-baseline.json`) only ratchets
downward unless an amendment raises it.

## Article III: Adequacy, not absolutism [gate]

Adequacy is risk-tiered and measured by **fault detection**: the mutation score over the code
in each tier. Line coverage is a diagnostic for finding untested code, never a target.
- **Critical code** (money, auth, data loss, safety) gets the strongest evidence: a high
  mutation score, properties, and proofs where they are cheap.
- **Standard code** gets a moderate mutation score.
- **Glue and configuration** get smoke or integration coverage only.

100% coverage is not a goal. Past about 90%, gains are logarithmic, while costs grow
linearly with every test. Where "complete" is required (R5), it means complete verification against
*defined obligations* (named mutants, partitions, requirements, or a stated structural criterion
over identified components), never unscoped coverage.

**Rigor profiles** set the evidence bar per path: R4 (Strict) adds survivor triage, failure-path
testing and independent review; R5 (High-Assurance) adds an assurance plan, bidirectional
traceability, history-mutant kills and an accountable human approval that no agent can supply.
Higher rigor means stronger evidence, not more tests.

## Article IV: Every test can fail, for the right reason [gate]

A test with no assertion, a tautological assertion, or a swallowed exception is a defect.
Expected values come from the **specification**, never from running the code under test.
An oracle anchored to the implementation cannot detect the implementation's faults.

## Article V: Marginal value (admission) [gate]

A new test is kept only if it detects something the existing suite does not: a mutant no
existing test kills, an uncovered partition or combination, or an untested requirement.
Otherwise, add a row to an existing table, strengthen an existing assertion, or do not
add it. Regression tests for real bugs may be marked *protected*; they still count against
the budget.

## Article VI: Behavior, not implementation [gate: mocks]

Test through public interfaces, and assert observable outcomes. Mock only at architectural
boundaries: network, disk, clock, randomness, and other teams' services. Never assert on
private state or on the sequence of internal calls. A test that breaks when the code is
refactored without a behavior change is a change detector, and it has negative value.

## Article VII: Generalize before you enumerate

When examples follow a rule, write the rule once:
- as a **property** checked over generated inputs, or
- as a **parametrized table** whose rows are the equivalence classes and boundaries of a
  declared partition model (`testing/partitions/`).

A new example that differs from an existing one only in input values is justified only if
the code branches on that difference.

## Article VIII: Proof over enumeration

Where a property is established by a proof, a type, a model check, or an exhaustive check
within stated bounds, the example tests inside its scope are redundant. Keep **one
conformance test** (a differential, trace, or model-based test) that ties the code to the
model, and state the bounds.

## Article IX: Catching vs hardening; the Prune step

Tests written to drive or debug a change are *catching* tests. Examples are TDD scaffolding,
reproductions, and exploratory probes. They are ephemeral. The TDD cycle is
**Red → Green → Refactor → Prune**: before a change is done, each new test is admitted
under Article V or deleted. Only *hardening* tests enter the suite.

## Article X: Levels and speed [gate: time]

The default test is small: one process, no network, no sleeps, deterministic, and fast.
Larger tests are few. Each is named for the risk that only it catches, and each runs in the
tier its cost allows (PR, merge, or nightly). If a lower-level test covers a condition, the
higher-level test for it goes.

## Article XI: Flakiness is a defect [gate]

A flaky test is quarantined the day it is seen, then fixed or deleted within the quarantine
window. No retry-until-green in the PR tier. A skipped test is either fixed or deleted; it
does not live forever.

## Article XII: Certified deletion [gate: probation]

Deleting tests is as normal as deleting code, and just as reviewable. A reduction must
preserve every obligation the full suite discharges (killed mutants, including
history mutants, plus any configured coverage), shown by a certificate that an independent
checker verifies. Removed tests are **demoted to probation** (the nightly tier) before
deletion. Deletions ship as their own change, never mixed with feature work.

## Article XIII: Governance

This constitution and `test-policy.toml` change only by amendment: a commit that edits them
and appends to the log below with a reason. CI runs `tmx gate` on every change. Every agent
reads the testing block in the agent instructions before writing a test. An agent may raise a
change's rigor, never lower it, and never waives an R4/R5 obligation or authorizes an R5 release. The suite is
audited against this constitution at least once a quarter.

## Amendment log

| Date | Version | Change | Reason |
|---|---|---|---|
| {{date}} | 1 | Adopted | Initial adoption |
