---
description: 'Should trigger test-ci'
tags: [trigger, test-ci, positive]
runs: 1
max_turns: 6
timeout_seconds: 150
allowed_tools: [Read, Glob, Grep, Skill]
---

CI is slow and flaky. restructure the test jobs into PR and nightly tiers and get rid of the retry loop
