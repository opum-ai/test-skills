# Rigor in test planning

The profiles are defined in `../../test-constitution/references/rigor-profiles.md`. The effective
level for a change is the highest of the project default, the tier of every path touched
(including the source covered by any test you change), and any `Rigor:` trailer. You may
raise it, never lower it.

| Level | Adds to the plan |
|---|---|
| R1 Minimal | Nothing is kept. Write a demo or smoke script and a *Limitations* list. Label the code R1; it is not admissible into R3+ paths until re-planned. |
| R2 Lightweight | Behaviors and targeted tests only. No partition model needed; the admission rule still applies. |
| R3 Standard | The full plan: behaviors, partitions, forms, budget, Prune, diff mutation. |
| R4 Strict | The **risk analysis** below; properties for every invariant; failure-path tests; every survivor in new code killed or triaged in `testing/survivors.json` with a reason; tests linked to requirement or risk ids; independent review. |
| R5 High-Assurance | The **assurance plan** below, agreed *before* implementation; bidirectional traceability (requirement ↔ code ↔ test ↔ hazard); formal verification of the selected critical properties (`coverage-proof` → proof-skills); the structural coverage criterion from the plan, measured by the project's qualified tool; all history mutants killed; human approval from the review record. **The agent never waives an obligation or declares release.** |

## R4 risk analysis (in the plan)

| Failure mode | Cause | Effect | Detection (which test or property) | Residual risk |
|---|---|---|---|---|
| Double redemption | concurrent redeem calls | balance negative | property: balance ≥ 0 under random interleavings, or proof-skills if concurrent | low after the fix |

Cover abnormal inputs, faults (I/O errors, timeouts), retries, partial failure and
recovery, and trust boundaries (every external input is validated, whatever the internal
invariants say).

## R5 assurance plan (before code)

1. **Scope and standards.** The components in scope, and the applicable standards (for
   example NPR 7150.2 SWE-219 for identified safety-critical components).
2. **Critical properties and hazards,** each with an id.
3. **Operating assumptions:** environment, inputs, timing.
4. **Acceptance obligations:**
   - the structural criterion and its tool;
   - the mutation floor (≥ 0.90);
   - every history mutant killed;
   - properties proven or model-checked, with bounds;
   - the independence of the assessor.
5. **The traceability matrix** skeleton.
6. **Approvers,** as listed in `[assurance] approvers`.

Missing evidence at the end is reported as **blocked**, not done.
