---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: Kill-set certificates, not coverage, justify deleting tests
tags:
  - architecture
summary: "A reduction is valid only if every mutant the full suite kills is still killed by a retained test, shown by a certificate an independent checker verifies."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:32.973Z
---

# Kill-set certificates, not coverage, justify deleting tests

## Status

Accepted (2026-09-26)

## Context

Test-suite minimization is set cover (NP-hard; Yoo & Harman 2012). The requirement being
covered determines what the reduction loses:
- **Statement coverage.** Coverage-based reduction cut 62.9% of tests but lost up to 20.5%
  of killed mutants. Kill-based reduction lost none, at a cost of 11.9 percentage points
  more tests (Shi et al., FSE 2014).
- **Coverage as a proxy.** Coverage correlates only weakly with fault detection once suite
  size is controlled for (Inozemtseva & Holmes, ICSE 2014).
- **Mutants as a proxy.** 73% of real faults couple to common mutants (Just et al., FSE 2014).
- **Mutants as guidance.** Suites selected for mutation score detect more real faults than
  random suites of the same size (Papadakis et al., ICSE 2018).

## Decision

`tmx analyze` solves weighted set cover over the kill matrix. It applies the standard
reductions, then exact branch-and-bound under a budget, with greedy plus a packing lower
bound as the fallback. It reports whether the result is optimal, and the gap when it is not.

Every plan carries:
- `certificate`: each obligation mapped to a retained witness test;
- `remove`: a per-test reason (zero-signal, duplicate, subsumed, jointly-covered);
- `curve`: size vs strength.

`tmx verify` re-derives validity from the matrix alone, so the optimizer is outside the
trusted base.

The matrix also includes **history mutants**: past fix commits that still reverse-apply to
HEAD. The certificate therefore preserves real historical faults too, which addresses the
17% of faults that couple to no classic mutant.

## Consequences

- Reductions are exactly as strong as the mutant set. A report must always state the
  operators, the sampling, the files, and the history depth.
- Surviving mutants are reported separately. The certificate never claims to find faults the
  full suite missed.
- Collecting a kill matrix costs roughly one targeted test run per mutant. `--per-line 1`
  (Google-style sampling) and `--operators extreme` (pseudo-tested functions) are the cheap
  first passes.
