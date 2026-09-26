---
name: coverage-proof
description: "Turn \"are these tests enough?\" and \"can these tests go?\" into stated, machine-checked claims - mutation kill-set certificates, partition and t-way covering-array completeness under an explicit uniformity hypothesis, property subsumption (one property replacing a table of examples), bounded-exhaustive checks under the small-scope hypothesis, differential tests against a reference model, confidence bounds for random testing, and TLA+/Lean proofs via proof-skills - then retire the example tests each claim subsumes, keeping one conformance test. Use this skill whenever the user asks to prove test adequacy, justify deleting tests mathematically, know how many tests a function really needs, replace many example tests with a property or model, get \"provable coverage\", or produce R4/R5 (Strict / High-Assurance) verification evidence - even if they just ask \"is this enough?\". It works on a named unit or cluster of tests; for auditing a whole suite use test-audit, and to cut or demote tests use test-reduce."
---

# coverage-proof

"We have 40 tests for `parse_duration`" says nothing. "`parse_duration` is complete under this
partition model at 2-way strength, a property kills every mutant the 40 examples killed, and
3 anchors remain" is a claim someone can check, and it justifies deleting 37 tests.

This skill produces claims of that second kind. The same claims serve as the evidence for
R4 and R5 rigor.

Every claim has three parts. A claim missing any part is a guess:
1. **A stated model and hypothesis.** The input partitions under uniformity, the
   interaction strength t, a small-scope bound, the generator's distribution, or the
   model's bounds. This is what "complete" is relative to.
2. **A trusted oracle.** The spec, a simpler reference model, an invariant, or a proof.
   Never the code under test.
3. **A non-vacuity check.** Show that the evidence *can fail*: it kills mutants, its
   sanity config fails, or its bug toggle fails. This is the discipline proof-skills
   applies to every model (ADR-0003 there).

`T=${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py`.

## The evidence ladder

Pick the weakest rung that answers the question. Cost rises as you climb.

| Rung | Claim it supports | How | Tool |
|---|---|---|---|
| 1. **Kill-set certificate** | "Removing these tests loses no fault detection **within this mutant scope**." | The set cover over the kill matrix, independently verified | `$T analyze`, `$T verify`, `$T compare` |
| 2. **Partition completeness** | "Every class and every t-way class combination is exercised, so under uniformity the suite equals the exhaustive product." | Declare the model and check covering; generate the minimum rows | `$T covering model.json --strength t [--generate]` |
| 3. **Property subsumption** | "This property checks everything these N examples checked." | Every example's input lies in the generator's domain, and the property's kills ⊇ the examples' kills | `$T subsumes matrix.json --by '<property>' --tests '<examples>'` |
| 4. **Bounded-exhaustive** | "Correct for **every** input up to size k" (small-scope hypothesis) | Enumerate all inputs within the bound against the oracle | a plain loop or `itertools`; see the reference |
| 5. **Differential vs a reference model** | "The implementation agrees with the simple model on generated inputs." Cedar-style. | A PBT comparing `impl(x) == model(x)`, with the model reviewed or proven | Hypothesis, fast-check or proptest; proof-skills `lean-model` differential testing |
| 6. **Proof / model check** | "The property holds for all states (TLA+ at bounds) or all inputs (a Lean theorem)." | Delegate to proof-skills `formal-verify`. It handles scoping, the correspondence map, the three-config sanity pattern and the trust audit. | proof-skills (installed separately) |
| 7. **Statistical bound** | "With n failure-free i.i.d. generated inputs, the failure probability under this distribution is < 3/n at 95%." | The rule of three. Say what the distribution is; it is not the operational profile unless you made it so. | arithmetic, stated in the claim |

## Workflow

1. **Frame the question.** Which unit or cluster, and which question?
   - Can these tests go? Use rungs 1–3.
   - Is this enough? Use rungs 2 and 4–7.
   - What evidence does R4/R5 need?
   Read the effective rigor (see `test-plan` step 0):
   - **R3:** rungs 1–3 are plenty.
   - **R4:** properties for every stated invariant, with each survivor triaged.
   - **R5:** rung 6 for the selected critical properties, rung 5 or trace validation to
     tie them to code, and every claim's assumptions listed.
2. **Model the input space** (`references/models.md`). Write
   `testing/partitions/<unit>.json`:
   - the parameters, the classes (valid *and* invalid), and the boundaries;
   - the constraints;
   - the hypothesis sentence.
   Take classes from the spec and from the code's branches. A class the code branches on
   but the spec never mentions is a finding: either the spec or the code is wrong.
3. **Build the evidence, weakest rung first.** For a cluster of example tests:
   1. Write the property or table that should replace them (patterns in
      `../test-reduce/references/consolidation.md`).
   2. Re-collect the matrix.
   3. Run `$T subsumes --by '<new test>' --tests '<old cluster>'`.
   4. If the verdict is `NOT SUBSUMED`, the listed mutants are exactly what the property
      misses. Strengthen the property, or keep the specific example that kills each one
      as an anchor.
4. **Check non-vacuity.**
   - For a property: it must kill mutants, as the matrix shows.
   - For a partition model: remove one class's row and confirm `covering` reports it
     missing.
   - For proof-skills models: the three configs.
   - For bounded-exhaustive: inject one wrong output into the oracle and see it caught.
5. **Record the claim** in `testing/claims/<unit>.json` (`references/claims.md`). One
   record per claim: the kind, the statement, the hypothesis and bounds, the oracle, the
   evidence commands and saved logs, the non-vacuity result, the tests it subsumes, the
   conformance test kept, and the assumptions. Claims are what R4 and R5 reviews read, and
   what later audits re-check.
6. **Retire what the claim subsumes, through `test-reduce`.** A proof or exhaustive check
   is not a license to skip the pipeline:
   - demote, probation, delete;
   - always keep **one conformance test** per claim: a differential, trace or model-based
     test tying code to model (Article VIII).
   Examples outside the claim's scope stay.
7. **Report.** For each claim, give the statement with its hypothesis, the rung, the
   evidence, the non-vacuity result, the tests subsumed and the conformance test kept.
   Also say what is **not** claimed: inputs outside the model, environment faults,
   performance.

## Routing to proof-skills

For concurrency, async interleavings, retries and idempotency, state machines, protocols,
or graph and DAG algorithms, the right evidence is a model or a proof, not more examples.
If the proof-skills plugin is installed (skills `formal-verify`, `tlaplus-model`,
`lean-model`, `proof-simplify`), hand over:
- **the concern:** the unit, and the cluster of tests that probe it;
- **the frozen properties:** take them from the tests' assertions and the spec.
- **the request:** workflow **W1** (verify), then **W5** (CI guard).
Then come back here and record the claim, with its bounds, the model ↔ code correspondence
and the trust base. A TLC pass is "no counterexample within bounds", never "correct".

If proof-skills is not installed, rungs 1–5 and 7 still work. Tell the user what rung 6
would add (unbounded or interleaving guarantees), and that `/plugin install
proof-skills@opum` provides it.

## Honesty rules

- A claim is only as good as its hypothesis. Write the hypothesis in the claim and in the
  report, every time.
- Subsumption is measured on the mutant set. State the operators, and remember that 17% of
  real faults couple to no mutant. That is why retirement goes through probation.
- Never derive an oracle by running the code under test. A property whose "expected" side
  calls the implementation proves nothing.
- A bounded result never becomes an unbounded claim without a proof or an argument, such as
  symmetry or a per-element property.
- "Exhaustive" means exhaustive *within the stated bound*, and the report says the bound.

## Reference files

- `references/models.md`: partition and decision-table models, state-transition coverage,
  choosing t, and the uniformity and regularity hypotheses (Gaudel), with worked examples.
- `references/claims.md`: the claim record schema and examples for each rung.
- `references/exhaustive-and-statistics.md`: bounded-exhaustive patterns, reference-model
  differential tests, the rule of three and its limits, and Good-Turing stopping.
