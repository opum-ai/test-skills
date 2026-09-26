---
# yaml-language-server: $schema=../../.lore/schemas/spec.schema.json
type: Spec
title: Engineering rigor profiles
tags:
  - rigor
  - governance
  - testing
status: draft
summary: "Five selectable rigor profiles, R1 Minimal to R5 High-Assurance, each a bundle of testing, evidence, review and gate obligations enforced per change and path."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:18:21.543Z
---

# Engineering rigor profiles

## Summary

A rigor profile is a named, selectable bundle of **obligations**:
- what must be verified;
- by what kind of evidence;
- reviewed by whom;
- enforced by which gate.

Users pick one per project, raise it for sensitive paths, and declare it per change. Every
skill in the plugin reads the effective profile and changes its behavior accordingly.

| Level | Profile | Intended use | Core expectation |
|---|---|---|---|
| **R1** | **Minimal** | Disposable experiments, spikes, feasibility checks | Demonstrate the idea, verify the basics, and state the limitations plainly |
| **R2** | **Lightweight** | Small, low-risk, easily reversible changes | Verify the affected behavior with targeted tests and a lightweight review |
| **R3** | **Standard** (default) | Routine production development | Meet acceptance criteria through adequate, lean testing, code review, and documented significant decisions |
| **R4** | **Strict** | High-impact, security-sensitive or hard-to-reverse changes | Explicit risk analysis, failure-path testing, triaged mutation survivors, independent review, and enforced gates |
| **R5** | **High-Assurance** | The most consequential safety-critical or mission-critical components | A defined assurance basis, validated and traced requirements, verification against defined obligations, independently assessed evidence, and an accountable human approval |

**The dividing line at the top:** Strict requires stronger engineering checks.
High-Assurance requires a defensible **assurance argument** plus the evidence that supports
it. Assurance means justified confidence backed by evidence that substantiates specific
claims (NIST's glossary definition; see the sources below).

**These are this project's internal profiles.** Selecting R5 does not establish
certification or compliance with DO-178C, ISO 26262, IEC 61508, IEC 62304 or NASA
NPR 7150.2. Those require qualified tools, planned processes and an external authority.
In particular, the plugin's `tmx` engine is not a qualified verification tool (in the sense
of DO-330). R5 raises the evidence bar and blocks release until a human accountable for
the component approves it.

## Requirements

### R-1: Rigor is evidence strength, not test count

Every level keeps the test constitution's economy articles: budget, marginal-value
admission, the Prune step, and certified deletion.

Higher rigor does **not** mean more tests. It means:
- stronger oracles;
- more of the suite expressed as properties, models and proofs;
- every surviving mutant accounted for;
- stricter deletion;
- more independent review.

A high-rigor suite should often be *smaller* and *stronger* than a careless one. If a
level's obligations can only be met by piling on examples, the plan is wrong, not the
level.

### R-2: Complete verification against defined obligations, never "complete coverage"

No level asks for "complete coverage" without a scope and a criterion. Code coverage
measures what tests execute, not whether their expectations are right: a test can execute
every line while checking a wrong expected value. Where a level asks for completeness, it
names the obligation set:
- the killed mutants and history mutants of a stated scope;
- the t-way combinations of a declared partition model;
- the requirements in a traceability matrix;
- a structural criterion, such as statement, branch or MC/DC, over *identified* components.

It also names the tool that measured the set. This is the same obligation model the `tmx`
certificate already uses (ADR-0002).

### R-3: Effective rigor resolves upward

For any change:

`effective rigor = max(project default, rigor of every path the change touches, rigor
declared for the change)`

- Path rigor comes from the `[[adequacy.tier]]` entries in `test-policy.toml`.
- Rigor declared for a change comes from a `Rigor: R<n>` trailer or the tracker task.
- An agent may **raise** the effective level on its own judgment, and should do so when it
  sees risk the policy did not anticipate.
- Only an amendment to `test-policy.toml` can **lower** a path's level (Article XIII).
- R1 code is not admissible into an R3+ path without being brought up to that path's
  level.

### R-4: Agents produce evidence; they never waive obligations

At every level, an agent may write the implementation, the tests and the evidence. From R4
upward:
- an agent may not waive an unmet obligation;
- an agent may not self-justify a budget exception;
- at R5, an agent may not authorize release.

Missing evidence produces a **blocked gate**, not a confident completion message. Approval
evidence must come from a record the agent cannot write:
- the code host's review record (required reviewers, CODEOWNERS);
- or a protected deployment environment;
- never a commit trailer, which the author can type.

A second agent reviewing the work counts as *independent review* at R4. It is **not**
independent verification and validation at R5. That requires independence from the
development organization, in NASA's IV&V sense: technical, managerial and financial.

### R-5: Every skill honors the profile

- `test-constitution` records the default and per-path levels in the policy.
- `test-plan` sizes its planning depth by level.
- `test-audit` judges compliance against the effective level of each path.
- `test-reduce` limits how aggressively it deletes by level.
- `test-ci` wires the level's tiers and approvals.
- `coverage-proof` supplies the proof-grade evidence R4 and R5 need.

Each skill states the level it worked at in its report.

## Design

### Obligations by level

Each row is enforced by the gate (**G**), produced by a skill (**S**), or reviewed by a
person (**P**).

| Obligation | R1 Minimal | R2 Lightweight | R3 Standard | R4 Strict | R5 High-Assurance |
|---|---|---|---|---|---|
| **Test planning** (S: test-plan) | none; a demo or smoke script | targeted tests for the affected behavior | a partition model for each changed unit; admission rule applied | R3 + **explicit risk analysis** (failure modes, abnormal and recovery paths, trust boundaries) | R4 + an **assurance plan**: applicable standards, critical properties, hazards, operating assumptions, acceptance obligations; all fixed *before* implementation |
| **Requirements traceability** (S/G) | — | — | each test names what it protects (Art. I) | each test is linked to a requirement or risk id | **bidirectional** traceability: requirement ↔ design ↔ code ↔ test ↔ hazard; the gate rejects an untraced test or an unverified requirement |
| **Oracles** (P/S) | stated limitations | spec-anchored expectations | spec-anchored (Art. IV) | + properties for every stated invariant | + reference model or formal spec for the critical properties, with differential or conformance tests |
| **Mutation adequacy** (G) | — | measured on the diff, advisory | tier thresholds (default 0.60 standard, 0.80 critical) | ≥ 0.80 in scope; **every survivor in changed lines triaged** (equivalent with a reason, or killed) | ≥ 0.90 in scope; every survivor triaged and recorded; **every history mutant killed** |
| **Structural coverage** (G) | — | — | a diagnostic only | branch coverage reported for changed critical code | the criterion stated in the assurance plan (for example 100% MC/DC for identified safety-critical components), measured with the project's qualified tooling; deviations need an approved rationale |
| **Failure-path testing** (S) | — | — | error handling of changed code | abnormal inputs, faults, timeouts, retries, recovery | + timing/resource analysis and representative-environment or hardware testing where relevant |
| **Formal methods** (S: coverage-proof, proof-skills) | — | — | optional where cheap (properties) | **recommended** for concurrency, state and protocol code; bounds stated | **required** for selected critical properties; scope, bounds, assumptions and trust base recorded; three-config sanity |
| **Test admission** (G, Art. V) | tests are ephemeral catching tests; nothing enters the suite | unique-kill advisory | unique-kill gated | gated; the protected list needs human sign-off | gated; each admitted test traced |
| **Forbidden smells** (G) | none gated | `no-assertion`, `tautology` | the policy default list | + `implementation-coupled`, `snapshot-literal`, `conditional-logic`; ≤ 2 mocks per test | as R4 |
| **Budget exceptions** (G, Art. II) | — | `Test-Budget:` trailer | `Test-Budget:` trailer | trailer **plus** human approval | an assurance-plan amendment plus approval |
| **Reduction / deletion** (S: test-reduce) | free | certificate; probation ≥ 3 days | certificate; probation 14 days / 20 runs | certificate over kills **and lines**; history mutants required; probation 30 days; a human reviews the deletion | deletion only with an assurance-case update showing every requirement and hazard keeps its verification; independent approval |
| **Flakiness** (G, Art. XI) | — | quarantine 14 days | quarantine 14 days | quarantine 7 days | zero tolerance: any quarantined test in scope blocks release |
| **CI tiers** (S: test-ci) | none required | PR tier | PR tier + nightly mutation and probation | + mutation on the diff in the PR tier | + full mutation and evidence archive per release; reproducible runs |
| **Review** (P) | self-review, limitations disclosed | lightweight review (self or agent) | code review by someone other than the author (human or independent agent) | **independent review** in a separate context; human sign-off on every waiver | **independent assessment** (IV&V-grade independence where required); accountable human approval of release |
| **Gate mode** (G) | advisory: reports, never blocks | blocks on Art. IV and budget | full default gate | full gate; waivers need platform approval | full gate; blocks until approval evidence from the code host is present |
| **Evidence kept** (S) | a limitations note | the PR description | findings.json + report; ADRs for significant decisions | + risk analysis and saved logs for every check claimed | + assurance case (claims → arguments → evidence), traceability matrix, and an evidence bundle retained per release |

### Where the levels come from, and how they line up with external schemes

These mappings are **indicative ("informed by", not "compliant with")**. External schemes
grade by *consequence of failure* and prescribe whole processes. Rigor profiles grade the
*engineering discipline* applied to a change. A team in a regulated domain applies its
standard's own requirements on top of the profile. Sources are in the
[State of the art](../reference/state-of-the-art-in-agentic-tdd-and-sustainable-test-suites.md) §6.

| Profile | NASA class (NPR 7150.2D) | DO-178C | ISO 26262 | IEC 61508 | IEC 62304 | FDA CSA | CC EAL |
|---|---|---|---|---|---|---|---|
| R1 Minimal | E (design concept, research) | E | QM | — | A (Ed. 2: I) | not high process risk | 1 |
| R2 Lightweight | D | E/D | QM / A | 1 | A/B | not high | 2 |
| R3 Standard | C (non-safety-critical) | D | A/B | 1/2 | B | mixed | 3–4 |
| R4 Strict | B, or safety-critical C | C/B | B/C | 2/3 | B/C | high: scripted | 4–5 |
| R5 High-Assurance | A/B safety-critical | B/A | C/D | 3/4 | C | high | 6–7 |

What the external schemes teach, and how each lesson appears in the profiles:
- **Coverage checks requirements-based tests; it is not the target.**
  - DO-178C §6.4.4 runs structural coverage analysis *on requirements-based tests*. A gap
    resolves one of four ways: add a test, fix the requirement, remove dead code, or
    justify. R4 and R5 use the same four outcomes for surviving mutants and coverage gaps
    (`testing/survivors.json`).
  - DO-178C's coverage ladder: statement at DAL C, adding decision at B and MC/DC at A.
  - ISO 26262-6 Table 9 highly recommends MC/DC at ASIL D. IEC 61508-3 highly recommends it
    at SIL 4.
- **100% is scoped and waivable.** NASA SWE-219 requires 100% MC/DC for *identified*
  safety-critical components, with a "technically acceptable rationale or a risk assessment"
  deviation approved by the Technical Authority. R5's "complete verification against defined
  obligations" follows the same shape.
- **Traceability grows with rigor.** NASA SWE-052 requires bidirectional traceability,
  including requirements ↔ hazards for Classes A–C. That appears here as
  - R3: each test names what it protects;
  - R4: tests are linked to requirement or risk ids;
  - R5: bidirectional traceability, including hazards.
- **Independence is graded.**
  - DO-178C objectives with independence: 2 at D, 5 at C, 18 at B, 30 at A.
  - NASA IV&V independence is technical, managerial *and* financial.
  - Here, an R4 independent review is satisfied by a separate reviewer context, and a
    human signs off waivers. R5 needs organizational independence where the domain
    requires it.
- **Low rigor is legitimate.** FDA CSA (final, 2025) endorses unscripted testing and
  "commensurate" records for lower process risk. CI logs are acceptable evidence, which is
  the R1–R2 evidence model. IEC 62304 Edition 2 is moving to two "process rigor levels".
  ISO/IEC/IEEE 29119-4 allows tailored conformance: choose a subset of techniques and
  coverage measures, with written justification.
- **Standard is not zero.** NIST IR 8397's minimum developer verification (80% statement
  coverage, with mutation and data-flow as stronger criteria) is a reasonable diagnostic
  floor for R3 critical paths. Google's 90% floor for changed-code coverage is another.
  R3 gates on mutation, and reports these as diagnostics.

### Configuration

```toml
# test-policy.toml
rigor = "R3"                        # project default

[[adequacy.tier]]
name = "critical"
paths = ["src/billing/**", "src/auth/**"]
rigor = "R4"                        # raises everything this tier touches
min_mutation_score = 0.85           # explicit values may raise a level's floor, never lower it

[assurance]                         # R4/R5 approval evidence (read by the gate)
approvers = ["@org/payments-leads"] # humans or teams whose approval counts
approval_source = "github-reviews"  # CI passes TMX_PR_APPROVERS from the review record
```

A change declares its own level with a `Rigor: R4` trailer, which can only raise the level.
The gate:
1. computes the effective level from the changed paths, the trailer and the default;
2. loads the profile's defaults (`tmx/rigor.py`);
3. overlays the explicit policy values, which may make a rule stricter but never looser. A
   level's floors (mutation minimum, forbidden smells, mock limit, triage, history kills,
   approval) only rise;
4. prints the level it enforced.

A test file changed on its own inherits the rigor of the source it covers, taken from the
kill matrix. Changing the tests of critical code is itself a critical change.

### Choosing a level (for the skills to ask or infer)

Ask, in order:
1. Will this code be thrown away? → R1.
2. If it is wrong, can it be reverted in minutes with no lasting harm? → R2.
3. Could it lose money or data, expose a secret, break authentication, or be hard to undo
   (migrations, public APIs, protocols)? → R4.
4. Could it hurt a person or lose a mission, or does a safety standard govern it? → R5.
5. Otherwise → R3.

Skills infer a level from the paths and the task, state it, and let the user override it.
They never silently choose a level below the path's configured level.

## Open questions

- Should R5 traceability be native to `tmx`, with requirement ids on tests (markers or
  docstrings) as obligations in the matrix, or read from an external requirements tool?
  The proposal is native markers first, so a reduction's certificate can preserve
  "each requirement keeps ≥ 1 verifying test" as another obligation kind.
- Should MC/DC be measured? No Python MC/DC tool is widely adopted. For C/C++ and Ada,
  qualified commercial tools exist. The proposal: R5 names the project's tool in its
  assurance plan, and `tmx` records its report as evidence rather than measuring MC/DC
  itself.
- Should per-developer "declared" rigor also be recordable in the Quest task, so planning
  can see it before code exists? The proposal is a `rigor:R<n>` label on the task.

## Sources

- NIST CSRC glossary, "assurance": grounds for justified confidence that a claim has been
  or will be achieved.
- NASA NPR 7150.2 (SWE-219 MC/DC for safety-critical components; SWE-052 bidirectional
  traceability) and NASA IV&V's three dimensions of independence.
- RTCA DO-178C and ISO 26262-6 structural coverage by level; IEC 61508-3; IEC 62304 software
  safety classes.
- The research behind the testing obligations:
  [State of the art in agentic TDD and sustainable test suites](../reference/state-of-the-art-in-agentic-tdd-and-sustainable-test-suites.md).
- Design decisions: [ADR-0002](../adr/0002-kill-set-certificates-not-coverage-justify-deleting-tests.md),
  [ADR-0003](../adr/0003-demote-before-delete-probation-tier-for-removed-tests.md),
  [ADR-0004](../adr/0004-constitution-as-prose-articles-plus-a-machine-enforced-policy.md).
