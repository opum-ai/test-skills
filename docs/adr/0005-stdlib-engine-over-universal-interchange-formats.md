---
# yaml-language-server: $schema=../../.lore/schemas/adr.schema.json
type: ADR
title: Stdlib engine over universal interchange formats
tags:
  - architecture
summary: "tmx is stdlib-only Python 3.9+ over test-matrix JSON, JUnit XML and Stryker/PIT reports, so it runs on any CI runner and any language can plug in."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.215Z
---

# Stdlib engine over universal interchange formats

## Status

Accepted (2026-09-26)

## Context

Projects span many languages, and agent-driven test bloat is language-agnostic. Per-language
mutation tools already exist:
- Stryker (JS/TS, C#, Scala), PIT (Java), cargo-mutants (Rust), go-mutesting and mutmut.

What none of them provides is the reduction math, the certificate, or the gate. JUnit XML
is the one report every runner emits. Stryker's JSON schema already carries per-test
`killedBy` / `coveredBy` data.

## Decision

- The engine is stdlib-only. The minimal TOML parser falls back for Python older than 3.11.
- Collectors:
  - **Python.** First-class: a pytest plugin records per-test coverage contexts and
    outcomes, and an AST mutator runs each mutant against only the tests that cover it,
    in throwaway copies of the project.
  - **Stryker.** Imported directly.
  - **Any runner.** JUnit XML for counts and time.
- Other mutation tools are adapter work against `test-matrix/1`.

## Consequences

- `collect-pytest` needs pytest and coverage in the *target* environment. Nothing else is
  installed.
- The Python mutator uses `ast.unparse`, so mutated copies lose formatting. Semantics and
  original line numbers are preserved.
