---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: Six skills split by greenfield, brownfield, CI and proof
tags:
  - architecture
summary: "Six skills: test-constitution and test-plan for new work, test-audit and test-reduce for existing suites, test-ci for pipelines, and coverage-proof for the math; the tmx engine lives in test-audit."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:25.398Z
---

# Six skills split by greenfield, brownfield, CI and proof

## Status

Accepted (2026-09-26)

## Context

Test sustainability has two very different entry points:
- a project adopting rules *before* it grows (greenfield);
- a project already collapsing under thousands of tests (brownfield).

CI design (tiers, selection, quarantine) is a third concern with its own vocabulary. The
mathematical justification for a small suite (certificates, partitions, proofs) is shared by
all three.

proof-skills (ADR-0001 there) showed that an orchestrator plus specialists triggers well,
and keeps each SKILL.md short enough to be read in full.

## Decision

Six skills, each with one job and a description that names its triggers:

| Skill | Job | Entry for |
|---|---|---|
| `test-constitution` | Adopt or amend the constitution and policy; install the agent-instructions block and gate | Governance, "set up testing rules" |
| `test-plan` | Plan a budgeted, partition-justified test set for a change; run TDD with the Prune step | New features, greenfield |
| `test-audit` | Measure a suite and CI against the constitution; produce findings, a reduction plan and a report | "Our tests are bloated / slow / flaky" |
| `test-reduce` | Apply the plan: consolidate, demote, delete with certificates; re-verify | "Cut the suite down" |
| `test-ci` | Tiers, affected-test selection, sharding, quarantine, ratchet, mutation on the diff | CI pipelines |
| `coverage-proof` | Certificates, partition models, covering arrays, property subsumption, bounded-exhaustive, confidence bounds; routes to proof-skills | "Prove these tests are enough" |

The shared engine `tmx` lives in `test-audit/scripts/` because measuring is that skill's
core. Sibling skills reach it at `${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py`.
Shared references (the constitution text and the smell catalog) live with
`test-constitution`.

## Consequences

- Six descriptions must be tuned for triggering against each other. The trigger eval sets
  include near misses between siblings, such as audit vs reduce.
- The plugin is one install, and skills cross-reference by relative path, as proof-skills does.
