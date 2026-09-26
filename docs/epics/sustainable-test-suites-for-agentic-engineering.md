---
# yaml-language-server: $schema=../../.lore/schemas/epic.schema.json
type: Epic
title: Sustainable test suites for agentic engineering
tags:
  - testing
  - skills
summary: "Six skills that govern test growth up front, plan lean tests for new work, audit existing suites and CI, and cut them down with certificates of no lost fault detection."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.376Z
---

# Sustainable test suites for agentic engineering

## Goal

Stop agent-driven development from burying projects under their own tests, and dig
existing projects out.

Coding agents add tests on every change and almost never remove them. A medium project
reaches thousands of tests. CI slows, flakes, and breaks on every refactor, while the extra
tests add little: agent-written tests barely change task outcomes, and agents detect stale
tests at about 36% F1. See [State of the art](../reference/state-of-the-art-in-agentic-tdd-and-sustainable-test-suites.md).
The fix is not better exhortation but **governance set up front and enforced by machines**.

The plugin delivers three things:
1. **A test constitution.** Thirteen articles, plus a machine-readable policy that a CI gate
   enforces. It covers budgets, risk-tiered adequacy, marginal-value admission of new tests,
   the Red → Green → Refactor → **Prune** cycle, and certified deletion.
2. **Planning for new work.** Test sets sized from risk and a declared input-partition
   model, using properties before examples, so "enough" is a stated, checkable claim rather
   than a feeling.
3. **Measured reduction of existing suites.** A per-test mutation kill matrix, a set-cover
   solver that finds the smallest subset preserving every kill, and a certificate an
   independent checker verifies. Removed tests are **demoted to a probation tier** before
   they are deleted, because kill-set-preserving reduction can still miss real regressions
   (Shi et al. 2018).

## Scope

In scope:
- **Greenfield.** The `test-constitution` and `test-plan` skills adopt governance and plan
  budgeted tests for new features.
- **Brownfield.** The `test-audit` and `test-reduce` skills measure a suite against the
  constitution and cut it down with certificates.
- **CI.** The `test-ci` skill sets up PR and nightly tiers, affected-test selection,
  sharding, flake quarantine, the budget ratchet, and mutation testing on the diff.
- **The math.** The `coverage-proof` skill handles kill-set certificates, partition and
  covering-array completeness, property subsumption, bounded-exhaustive checks, and
  statistical confidence. It routes concurrency and state properties to proof-skills.
- **The `tmx` engine.** Stdlib-only Python that runs anywhere Python 3.9+ does:
  - collectors for pytest (per-test coverage and a kill matrix) and Stryker (JS/TS, C#, Scala);
  - JUnit XML for counts and time, for any runner;
  - analysis, certificate verification, smells, clones, covering arrays, the gate, and the baseline.
- **Evaluation.** Fixtures with bloated suites, with-skill and without-skill benchmarks, and
  trigger evals.

Out of scope for v0.1:
- Native mutation collectors for Go, Rust and Java. These projects import the output of
  their own tools (cargo-mutants, PIT, go-mutesting) through the interchange format, with a
  thin adapter still to be written.
- Hosted services and dashboards.
- Rewriting production code. That belongs to proof-skills' `proof-simplify`.

## Design principles

1. **Evidence, not opinion.** Every deletion carries a certificate. Every adequacy claim
   names its mutant set, its partition model and hypothesis, or its proof bounds.
2. **Reversible first.** Selection and tiering come before deletion, and deletion comes
   only after probation.
3. **Gates, not prose.** Anything in the constitution a machine can check is in
   `test-policy.toml` and enforced in CI. Prose covers the rest.
4. **Lean by default for agents.** The agent instructions block puts the admission rule
   and the Prune step in front of every agent that writes a test.
5. **Stand on proof-skills.** Concurrency and state properties route to `formal-verify`,
   and proven properties justify retiring the example tests they subsume.

## Stories

- [tmx test-matrix engine](../stories/tmx-test-matrix-engine.md)
- [test-constitution skill](../stories/test-constitution-skill.md)
- [test-plan skill](../stories/test-plan-skill.md)
- [test-audit skill](../stories/test-audit-skill.md)
- [test-reduce skill](../stories/test-reduce-skill.md)
- [test-ci skill](../stories/test-ci-skill.md)
- [coverage-proof skill](../stories/coverage-proof-skill.md)
- [Skill evaluation suite](../stories/skill-evaluation-suite.md)

## Decisions

- [ADR-0001 Six skills split by greenfield, brownfield, CI and proof](../adr/0001-six-skills-split-by-greenfield-brownfield-ci-and-proof.md)
- [ADR-0002 Kill-set certificates, not coverage, justify deleting tests](../adr/0002-kill-set-certificates-not-coverage-justify-deleting-tests.md)
- [ADR-0003 Demote before delete](../adr/0003-demote-before-delete-probation-tier-for-removed-tests.md)
- [ADR-0004 Constitution as prose articles plus a machine-enforced policy](../adr/0004-constitution-as-prose-articles-plus-a-machine-enforced-policy.md)
- [ADR-0005 Stdlib engine over universal interchange formats](../adr/0005-stdlib-engine-over-universal-interchange-formats.md)
- [ADR-0006 Reuse proof-skills as-is](../adr/0006-reuse-proof-skills-as-is-specialize-only-test-facing-proof.md)
