# Engineering rigor profiles (agent-facing summary)

The design record is `docs/specs/engineering-rigor-profiles.md` in the test-skills repo.
This is the operational summary every skill uses.

| Level | Profile | Use for | Core expectation |
|---|---|---|---|
| R1 | Minimal | spikes, experiments, feasibility | Demonstrate the idea, verify the basics, and disclose the limitations. No kept tests. |
| R2 | Lightweight | small, low-risk, easily reversible changes | Targeted tests for the affected behavior; a lightweight review. |
| R3 | **Standard (default)** | routine production development | Lean, adequate tests (constitution Articles I–XIII), code review, and significant decisions recorded. |
| R4 | Strict | security, money, data, or hard-to-reverse changes | Risk analysis, failure-path tests, properties for invariants, every survivor triaged, independent review, and human-approved waivers. |
| R5 | High-Assurance | safety- or mission-critical components | An assurance plan before code, bidirectional traceability, verification against defined obligations, formal methods for the selected properties, independent assessment, and an accountable human approval. |

**Effective level** = max(the policy `rigor`, the `rigor` of every tier a change touches
(a test file counts as touching the source it covers), and any `Rigor: R<n>` trailer).
Agents may raise it, never lower it. Only an amendment can lower a path's level.

**Rigor is evidence strength, not test count.** Higher levels require stronger oracles,
properties, proofs, triage, stricter deletion and more independence. They do not require
more examples.

## What the gate enforces (`tmx/rigor.py`; explicit policy may tighten, never loosen)

| Rule | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| mode | advisory (reports R3's findings, blocks nothing) | block | block | block | block |
| forbidden smells | (R3's, as warnings) | no-assertion, tautology | + swallowed-exception, sleep, skipped | + implementation-coupled, snapshot-literal, conditional-logic | as R4 |
| max mocks per test | — | — | 3 | 2 | 2 |
| mutation floor (tiers at this level) | — | — | 0.60 | 0.80 | 0.90 |
| unique-kill admission | — | — | yes | yes | yes |
| survivors in changed code triaged | — | — | — | yes | yes |
| history mutants must be killed | — | — | — | — | yes |
| budget exception | trailer | trailer | trailer | trailer + approval | trailer + approval |
| accountable approval required | — | — | — | — | yes (from the review record) |
| quarantine | — | 14 d | 14 d | 7 d | any entry blocks |
| probation before deletion | none | 3 d / 3 runs | 14 d / 20 runs | 30 d / 30 runs, `--lines` | 30 d / 30 runs, plus assurance-case update and approval |

**Approvals** reach the gate only through `TMX_PR_APPROVERS`, which CI sets from the code
host's review record, filtered by `[assurance] approvers`. A commit trailer never counts:
the author can type one.

**"Complete" always means complete against defined obligations:** named mutants,
partitions at t-way, traced requirements, or a stated structural criterion over identified
components (for example NASA SWE-219: 100% MC/DC for identified safety-critical
components, with approved deviations). It never means unscoped coverage.

**Not certification.** R5 does not make software DO-178C, ISO 26262, IEC 61508, IEC 62304
or NPR 7150.2 compliant. `tmx` is not a qualified tool.
