---
description: 'Should trigger test-constitution'
tags: [trigger, test-constitution, positive]
runs: 1
max_turns: 6
timeout_seconds: 150
allowed_tools: [Read, Glob, Grep, Skill]
---

agents keep adding tests to this repo on every change. set up rules so that stops going forward and CI enforces it
