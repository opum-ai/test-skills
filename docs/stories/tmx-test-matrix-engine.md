---
type: Arc
title: tmx test-matrix engine
tags:
  - skills
summary: "The stdlib-only tmx engine: kill matrices, certified reduction, smells, covering arrays, probation and the rigor-aware gate."
tasks:
  - ts-3
  - ts-11
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:34.016Z
lore_task_status: todo
---

# tmx test-matrix engine

## Goal

Give every skill one deterministic engine for measuring and reducing test suites, so every claim a skill makes is backed by a re-runnable command.

## Acceptance criteria

- `collect-pytest` builds per-test coverage and kill matrices in throwaway copies, with a control run that rejects a non-green harness
- `analyze`/`verify`/`compare`/`subsumes` produce and independently check certificates
- `gate` enforces test-policy.toml at the effective rigor level
- The engine's own suite runs in under 10 seconds and is itself mutation-audited

## Tasks

<!-- lore:tasks:begin -->
| Task | Title | Status |
|---|---|---|
| [TS-3](../../.quest/completed/TS-3.json) | tmx test-matrix engine | Done |
| [TS-11](../../.quest/tasks/TS-11.json) | Bring the tmx engine up to its own R4 critical-tier floor | To Do |
<!-- lore:tasks:end -->

## Notes
