# Building the matrix in other languages

The analysis only needs `test-matrix/1` (see `scripts/tmx/matrix.py`). Mutants need
`killed_by` test ids. Coverage is optional.

| Language | Tool | Per-test kills | How |
|---|---|---|---|
| Python | built in (`collect-pytest`) | yes | pytest plugin, plus AST mutants run against their covering tests only |
| JS / TS | Stryker | yes | `stryker run` with `coverageAnalysis: "perTest"`, **`disableBail: true`**, and `reporters: ["json"]`, then `tmx.py import-stryker reports/mutation/mutation.json`. See "Stryker, verified" below |
| C#, Scala | Stryker.NET, Stryker4s | yes | same JSON schema, same importer |
| Java / Kotlin (JVM) | PIT | yes | `-DfullMutationMatrix=true -DoutputFormats=XML`, then `tmx.py import-pit target/pit-reports/mutations.xml` (reads `killingTests`) |
| Rust | cargo-mutants | suite-level only | `mutants.out/outcomes.json` says caught/missed per mutant, not which test. Use it for **score and survivors**. For per-test kills, run `cargo nextest` per mutant with JUnit output, or scope the audit to smells/clones |
| Go | go-mutesting / gremlins | suite-level only | same as Rust |
| Anything | JUnit XML | none | counts, time and skips for the gate and inventory. Static smells and clones for JS/TS and Python |

When per-test kills are unavailable, say so in the verdict strip and **do not produce a
certificate**. Redundancy can then only be reported as *candidates* (clones, smells,
zero-assert tests), never as certified removals.

## Stryker, verified on a real project (`evals/fixtures/ts-bloated-cart`)

This was verified with Stryker 10 and `@stryker-mutator/vitest-runner` on vitest 4.1 and 3.2.
The fixture's `stryker.config.json` is deliberately left at Stryker's defaults (it is an eval
fixture). Add `"disableBail": true` before collecting a matrix.

**Required settings.**
- **`coverageAnalysis: "perTest"`.** Without it there are no per-test kill sets.
- **`disableBail: true`.** Stryker's default stops at the first failing test, so every
  mutant names exactly one killer. The other tests then look zero-signal, and the removal
  reasons are wrong. The importer refuses such a report; `--allow-bail` overrides that.
- **The `json` reporter.** It writes `reports/mutation/mutation.json`.

**Known trap: Stryker 10 with vitest 5 is silently vacuous.** The tests run against
unmutated code: the same suite scored **6.5% on vitest 5 and 97.4% on vitest 4.1**, with no
error. If most mutants survive while being covered by many tests, the importer refuses the
report and names this cause (`--allow-low-score` overrides it). Pin vitest ≤ 4.x until the
runner supports 5.

**Domain faults.** Stryker never changes a rate, a threshold or the order of two rules. Use
`tmx faults faults.json --cmd "npx vitest run --reporter=junit --outputFile={junit}" --matrix
.tmx/matrix.json -o .tmx/matrix.json`, which merges the faults into the imported Stryker matrix.
In the benchmark, every agent auditing the TypeScript fixture needed this: Stryker alone certified
10 tests that would miss 9 plausible money bugs.

**No `verify --rerun` for Stryker.** The empirical replay is pytest-only. The equivalent is to
exclude the demoted tests (a vitest `exclude` pattern or a `*.probation.test.ts` rename), re-run
Stryker, re-import, and run `tmx compare before.json after.json`. Stryker mutants carry
stable keys (`file:line:column:mutator:replacement`), so the compare is exact.

**What else works for JS/TS:**
- **Static smells.** Covered: no-assertion; tautology (the same literal or name on both sides;
  calls are a determinism check and are fine); weak assertions (`typeof`, `toBeDefined`,
  `toBeTruthy`, `not.toBeNull`); `it.skip`/`xit`; snapshots; timers; mocks and spies; and
  private-state or call-count coupling (`as any).`, `toHaveBeenCalledTimes`).
- **The gate**, over JUnit output (`vitest --reporter=junit`).

**Not yet for JS/TS:** clone clustering (it is Python-AST only) and an automatic probation hook
(see `../../test-reduce/references/probation-other-runners.md`).
