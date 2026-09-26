---
description: 'Near miss: should NOT trigger test-audit'
tags: [trigger, test-audit, negative]
runs: 1
max_turns: 6
timeout_seconds: 150
allowed_tools: [Read, Glob, Grep, Skill]
---

configure pytest-xdist so tests run in parallel
