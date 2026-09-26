---
description: 'Should trigger test-audit'
tags: [trigger, test-audit, positive]
runs: 1
max_turns: 6
timeout_seconds: 150
allowed_tools: [Read, Glob, Grep, Skill]
---

run a health check on the tests and CI: redundancy, flaky stuff, mocks, the lot. report only
