<!-- test-skills:constitution:begin -->
## Testing rules (TEST-CONSTITUTION.md, enforced by `tmx gate`)

Before writing or changing a test:
1. **Name what it protects.** Every test protects a requirement, contract, past bug or listed
   risk (Art. I). If you cannot name one, do not write it.
2. **Admit only marginal value.** Keep a new test only if it catches something the suite does
   not (Art. V). A new example that varies only input values is justified only if the code
   branches on that difference. Otherwise add a row to the existing table or property (Art. VII).
3. **Prune before you finish.** TDD is Red → Green → Refactor → **Prune** (Art. IX). Delete
   scaffolding and probe tests, or fold them into tables. Report `tests +N/-M` in the summary.
4. **Assert behavior from the spec.** No asserts on private state or internal call order. Mock
   only network/disk/clock/randomness (Art. VI). Expected values come from the spec, never
   from running the code (Art. IV).
5. **Stay in budget.** At most {{max_new}} new tests per change without a `Test-Budget: <reason>`
   trailer (Art. II). No sleeps, no retries-to-green, no skipped tests (Art. X, XI).
6. **Work at the effective rigor.** The effective level is the highest of the project default ({{rigor}}),
   the tier of every path you touch, and any `Rigor:` trailer. You may raise it, never lower it. At
   R4/R5, never waive an obligation or claim approval; missing evidence means the gate stays red.
7. **Never delete tests to get green.** Removing tests is its own change, with a `tmx`
   certificate (Art. XII). Use the test-reduce skill.
<!-- test-skills:constitution:end -->
