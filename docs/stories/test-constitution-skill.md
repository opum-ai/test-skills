---
type: Arc
title: test-constitution skill
tags:
  - skills
summary: "Adopt or amend a test constitution: thirteen articles, a machine-enforced policy, rigor profiles, an agent block and an edit-time hook."
tasks:
  - ts-4
  - ts-2
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.538Z
lore_task_status: done
---

# test-constitution skill

## Goal

Set the rules of test economy before a suite grows, and make machines enforce them.

## Acceptance criteria

- `adopt.py` writes TEST-CONSTITUTION.md, test-policy.toml and the managed agent block idempotently
- Adoption never turns CI red on day one
- Rigor profiles R1–R5 are selectable per project and per path

## Tasks

<!-- lore:tasks:begin -->
| Task | Title | Status |
|---|---|---|
| [TS-4](../../.quest/completed/TS-4.json) | test-constitution skill | Done |
| [TS-2](../../.quest/completed/TS-2.json) | Define engineering rigor profiles R1-R5 and wire them into the skills | Done |
<!-- lore:tasks:end -->

## Notes
