---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: Constitution as prose articles plus a machine-enforced policy
tags:
  - architecture
summary: "TEST-CONSTITUTION.md holds thirteen articles; test-policy.toml holds every checkable number; tmx gate enforces them in CI and a managed block briefs agents."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.135Z
---

# Constitution as prose articles plus a machine-enforced policy

## Status

Accepted (2026-09-26)

## Context

Advisory rules decay, and agents in particular follow gates better than prose:
- Claude Code's own best practices rank hooks and CI gates above instructions.
- A machine-readable TDD manifesto enforced by a deterministic engine outperforms prompting
  (Hasanli et al. 2026).
- Plain TDD instructions without test context *raised* regressions (TDAD 2026).

GitHub spec-kit's constitution shows that "articles up front" works as a pattern. But its
testing articles (III test-first, IX integration-first) say nothing about test *economy*:
no budget, no marginal-value rule, no deletion. OpenAI Codex's AGENTS.md carries concrete
anti-bloat bans, which shows that short, specific rules are adoptable.

## Decision

- `TEST-CONSTITUTION.md` holds thirteen numbered articles, each with the rule, the rationale
  and its source, and whether it is machine-enforced.
- `test-policy.toml` holds the numbers:
  - budgets: max tests, suite seconds, new tests per PR;
  - risk tiers: path globs with minimum mutation scores;
  - admission: forbidden smells, maximum mocks, the unique-kill requirement, protected globs;
  - flakiness: the quarantine window and maximum skips;
  - probation.
- `tmx gate` reads the policy and CI evidence (JUnit, matrix, git base) and reports each
  violation with its article.
- `.test-baseline.json` is the ratchet. Growth beyond the per-PR limit needs a
  `Test-Budget: <reason>` trailer.
- A managed block in CLAUDE.md / AGENTS.md gives agents the six rules they need while
  writing tests.

Amendments are commits to both files, with a rationale line in the constitution's
amendment log.

## Consequences

- A project can adopt the whole constitution with defaults in one step, then tune the
  numbers.
- Every gate failure names the article it enforces, so the fix is discoverable.
- Articles that no machine can check yet (for example, oracle anchoring) stay prose.
  `test-audit` reviews them.
