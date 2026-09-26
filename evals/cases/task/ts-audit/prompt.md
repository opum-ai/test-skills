---
description: 'ts-audit'
tags: [task, test-audit]
runs: 1
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

This is a small TypeScript service with a Vitest suite that agents have been growing on every change. It's getting brittle and we don't trust it. Audit the tests: how many do we actually need, which ones, and what's wrong with the rest? Stryker is already set up (npm run mutate). Don't change the code or the tests yet.
