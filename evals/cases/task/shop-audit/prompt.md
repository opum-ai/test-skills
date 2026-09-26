---
description: 'shop-audit'
tags: [task, test-audit]
runs: 1
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Our test suite in this repo has gotten out of hand. Agents have been adding tests with every change, every refactor breaks dozens of them, and nobody trusts CI. Audit the tests and the CI setup and tell me how many of these tests we actually need and which ones. Don't change any tests or code yet; I want the analysis first.
