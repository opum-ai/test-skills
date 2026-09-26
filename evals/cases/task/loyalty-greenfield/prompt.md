---
description: 'loyalty-greenfield'
tags: [task, test-plan]
runs: 1
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Implement the tiered loyalty feature described in SPEC.md, test-first. The public API from SPEC.md should be importable from the `loyalty` package. We've been burned by test bloat before, so keep the test suite sustainable while still covering what matters.
