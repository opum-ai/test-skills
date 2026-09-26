---
name: test-plan
description: Plan and write the smallest test set that adequately verifies a new feature, bug fix or module - derive behaviors from the spec, model input partitions and boundaries, choose property vs parametrized table vs single example, size a test budget, then run TDD as Red-Green-Refactor-Prune so scaffolding tests never pile up - at the rigor level the change requires (R1 Minimal to R5 High-Assurance). Use this skill whenever the user asks to write tests for new code, do TDD, "add tests for this feature", implement something from a spec with tests, decide how many or which tests a change needs, or wants test-first development that does not bloat the suite - including when an agent is about to add tests as part of any feature work in a repo with a TEST-CONSTITUTION.md. For shrinking an existing suite use test-reduce; for suite-wide measurement use test-audit.
---

# test-plan

Incremental TDD adds one test per thought and deletes none. After a hundred changes the
suite is a transcript of every thought anyone had. The cure is to **plan the test set
from the behavior space before writing any test**. Then TDD writes tests *toward the
plan*, and a final **Prune** step removes whatever the plan did not need.

The target is not "as many tests as possible" or "100% coverage". It is **every named
behavior verified by exactly enough evidence**:
- each equivalence class and boundary represented once;
- invariants stated as properties;
- nothing that duplicates what the existing suite already catches.

## Step 0: Rigor and constitution

Read `TEST-CONSTITUTION.md` and `test-policy.toml` if present. Resolve the change's
**effective rigor**: the highest of the project default, the tier of every path you will
touch, and anything the user or task declared. See the rigor spec summary in
`references/rigor.md`. If the change carries money, auth, data loss or irreversibility
risk the policy did not foresee, raise the level. Never lower it. State the level in your
first message.

| Level | Planning depth |
|---|---|
| R1 Minimal | No kept tests. A demo or smoke script, with limitations stated. Tests written while exploring are thrown away. |
| R2 Lightweight | Targeted tests for the affected behavior. Steps 1, 4 and 5 only. |
| R3 Standard | The full workflow below. |
| R4 Strict | R3, plus a **risk analysis** (failure modes, abnormal and recovery paths, trust boundaries), properties for every invariant, and every surviving mutant in new code triaged. |
| R5 High-Assurance | R4, plus an **assurance plan** fixed before code (standards, critical properties, hazards, assumptions, acceptance obligations), requirement ids traced on every test, formal verification of the selected properties via `coverage-proof` / proof-skills, and a human approval the agent cannot give. |

## Workflow

1. **Behaviors.** Turn the spec or acceptance criteria into a numbered list of observable
   behaviors: B1, B2 and so on. Each is one sentence a user or caller would recognize.
   These are what tests protect (Article I). Mark each one's risk (critical / standard /
   glue) from the policy tiers. If behaviors are unclear, ask. A test of a guessed behavior
   is a change detector in waiting.
2. **Partition model** (`references/partitioning.md`). For each unit with non-trivial input
   logic:
   - list its parameters;
   - give each parameter's equivalence classes, *including invalid classes*;
   - name the boundaries (on, just below, just above);
   - write down the constraints.
   Save the model to `testing/partitions/<unit>.json` and state its hypothesis: "uniformity
   within each class" plus the interaction strength t, which defaults to 2 and is 3 for
   critical interactions. Then run:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py covering testing/partitions/<unit>.json --strength 2 --generate
   ```
   The generated covering array is the **row budget**. Under the model's stated hypothesis,
   rows beyond it add nothing. Decision tables and state-transition models are partition
   models too; see the reference.
3. **Choose the form of each behavior's evidence** (`references/properties.md`):
   - **Property.** For invariants, round-trips, idempotence, monotonicity, and conservation
     (totals, balances, counts). Also for model equivalence against a simple reference, and
     metamorphic relations. One property replaces a whole family of examples.
   - **Table.** For the partition rows: one parametrized test per unit and behavior, one
     row per class or boundary, with `ids` that name the class.
   - **Single example.** For an anchor the spec states literally ("100 points = $1"), or a
     reproduction of a reported bug. Add the latter's exact id to `testing/protected.txt`, as its own reviewed change.
   - **Integration or contract test.** Only for wiring across an architectural boundary.
     At most one per boundary per behavior (Article X).
   - **No test.** When a type, a schema, an existing test or a proof already guarantees it.
     Say which one.
4. **Budget.** Count the planned test cases. That is the change's budget.
   - Compare it with the policy's `max_new_tests_per_pr`. If the plan exceeds it, first
     look for rows that share a class, examples a property already covers, and integration
     tests that repeat unit coverage. Only then justify the rest with a
     `Test-Budget: <reason>` trailer.
   - Also check what the **existing suite already covers**. Run the existing tests against
     the untouched code, or look them up in the matrix, and drop planned rows it already
     pins.
   - Write the plan (`references/plan-template.md`) into the PR description or
     `testing/plans/<change>.md` before writing code.
5. **TDD toward the plan: Red → Green → Refactor → Prune.**
   - **Red / Green / Refactor** as usual. Write each planned table or property first, and
     watch it fail for the right reason: an assertion, not an import error.
   - **Catching tests are allowed while you work.** Probes, reproductions and one-off
     examples are fine as scaffolding. They are ephemeral (Article IX).
   - **Prune, before the change is done:**
     - delete every test not in the plan, or fold it into a planned table as a row it
       justifies;
     - merge tables that ended up testing the same class;
     - re-run the suite.
     Pruning trims what the plan did not need. It does not lower the plan. Rows that
     `tmx covering` generated to reach the model's strength t stay, even when today's mutants
     don't separate them. A mutant set only samples the faults, while the covering array is the
     adequacy claim you made in step 3. To drop to a lower t, change the plan and say why
     in the report.
   - **Admission check.** Measure the new tests' marginal value with mutation on the changed
     source:
     ```bash
     T=${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py
     python -m ... $T collect-pytest --src <changed module> --tests tests -o .tmx/change.json --per-line 2
     $T score .tmx/change.json --survivors
     ```
     Every new test should kill at least one mutant no older test kills (Article V). For
     **data-only additions**, such as a new tax region or rate row, the new literal is itself
     the mutant: numeric strings like `Decimal("0.0825")` are mutated. Add the row to the
     existing table rather than writing a new test function. If one
     does not, drop it or merge it. Survivors in new code are either real gaps (add the
     *row* or *assertion* that kills them) or equivalent (at R4+, record them in
     `testing/survivors.json` with a reason).
   - Run `tmx gate --base <base>` locally if the project has a policy.
6. **Report.** In the final message and the PR description:
   - behaviors → tests map;
   - the partition models and t;
   - planned vs written vs **pruned** (`tests +N / −M`);
   - the mutation score on changed code, with survivors triaged;
   - the rigor level, and what it required.
   At R4 and R5, include the risk analysis or assurance plan, and name what still needs
   human sign-off.

## Rules of thumb that prevent bloat

- A new example that differs from an existing one only in values needs the code to branch
  on that difference. Otherwise it is a row in the same class; delete it (this is the
  daily.dev rule).
- Test through the public API. Mock only network, disk, clock and randomness.
- Expected values come from the spec or a simpler model, never from running the new code
  and pasting the output. An oracle anchored to the code cannot catch the code's bugs.
- If a higher-level test and a lower-level test catch the same thing, keep the lower one.
- A test you would not mind deleting tomorrow was scaffolding. Delete it today.

## Reference files

- `references/partitioning.md`: category-partition, boundary values, invalid classes,
  decision tables, state-transition coverage, t-way interaction, and the model JSON format.
- `references/properties.md`: property patterns with pytest/Hypothesis and fast-check
  examples, stateful testing, and how to keep generators honest.
- `references/plan-template.md`: the plan and report template.
- `references/rigor.md`: what each rigor level adds to planning, and the R4 risk-analysis
  and R5 assurance-plan templates.
