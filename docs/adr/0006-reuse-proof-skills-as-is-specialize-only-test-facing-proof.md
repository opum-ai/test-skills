---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: Reuse proof-skills as-is; specialize only test-facing proof
tags:
  - architecture
summary: "proof-skills is used as-is for TLA+/Lean; this plugin adds only the test-facing layer that retires tests subsumed by proven properties."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.296Z
---

# Reuse proof-skills as-is; specialize only test-facing proof

## Status

Accepted (2026-09-26)

## Context

proof-skills already does TLA+ and Lean modelling well, with a model-to-code
correspondence, reproduction, a three-config sanity pattern and a trust audit. Its
`proof-simplify` turns proofs into *code* deletions.

The missing piece is the mirror image: turning proofs and exhaustive checks into *test*
deletions. Industry practice pairs proofs with conformance testing rather than replacing
tests outright:
- Cedar pairs Lean proofs with about 100M nightly differential tests.
- AWS IAM authorization ran differential testing against 10^15 production samples.
- MongoDB generated 4,913 tests from a TLA+ model and reached 100% branch coverage, against
  21% for handwritten tests.

## Decision

`coverage-proof` owns the test-facing proof layer:
- kill-set certificates;
- partition models with covering arrays, under stated uniformity and t-way hypotheses;
- property subsumption: one property plus an oracle replaces a table of examples;
- bounded-exhaustive checks under the small-scope hypothesis;
- statistical bounds for random testing (the rule of three).

For concurrency, state machines and protocols it routes to proof-skills `formal-verify`
(W1/W5) when installed. Once a property is verified, the example tests inside its scope
are retired, except for **one conformance test**: a differential test, trace validation,
or model-based test that ties the code to the model.

If proof-skills is not installed, `coverage-proof` still delivers everything except
TLA+/Lean. It says what an install would add.

## Consequences

- There is no duplicated modelling machinery, and proof-skills improvements flow through.
- There is a soft dependency: the skills detect proof-skills by checking whether its skills
  are available and degrade gracefully.
