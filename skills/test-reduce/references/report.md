# Reduction report contract

It builds on `../../test-audit/references/report.md`. Differences:

1. **Verdict strip:** "tests 172 → 31 in the PR tier (−82%), suite 4.1s → 0.7s; 0 of 171
   killed mutants lost (8 operators + 3 historical faults); 96 on probation until
   2026-10-10."
2. **Stages table.** One row per stage (consolidate, demote, delete): tests removed or
   changed, the evidence command, its result, and the saved log.
3. **Consolidations.** Each cluster shows its before count, what it became (a table, a
   property or a merge), a diff snippet under 20 lines, and its compare result.
4. **Probation.** How many tests, why (the reason counts), when they become due, and any
   promotions back, each with the regression it caught.
5. **Strength.** Mutation score before and after, per tier. Survivors are unchanged, or
   list the new kills.
6. **Budget.** The old and new baselines and `max_tests`, and the amendment line added.
7. **What this does not prove.** The mutant scope, and why probation exists.
8. **Re-run.** Exact commands.
