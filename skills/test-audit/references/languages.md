# Building the matrix in other languages

The analysis only needs `test-matrix/1` (see `scripts/tmx/matrix.py`). Mutants need
`killed_by` test ids. Coverage is optional.

| Language | Tool | Per-test kills | How |
|---|---|---|---|
| Python | built in (`collect-pytest`) | yes | pytest plugin, plus AST mutants run against their covering tests only |
| JS / TS | Stryker | yes | `stryker run` with `coverageAnalysis: "perTest"` and `reporters: ["json"]`, then `tmx.py import-stryker reports/mutation/mutation.json` |
| C#, Scala | Stryker.NET, Stryker4s | yes | same JSON schema, same importer |
| Java / Kotlin (JVM) | PIT | yes | `-DfullMutationMatrix=true -DoutputFormats=XML`, then `tmx.py import-pit target/pit-reports/mutations.xml` (reads `killingTests`) |
| Rust | cargo-mutants | suite-level only | `mutants.out/outcomes.json` says caught/missed per mutant, not which test. Use it for **score and survivors**. For per-test kills, run `cargo nextest` per mutant with JUnit output, or scope the audit to smells/clones |
| Go | go-mutesting / gremlins | suite-level only | same as Rust |
| Anything | JUnit XML | none | counts, time and skips for the gate and inventory. Static smells and clones for JS/TS and Python |

When per-test kills are unavailable, say so in the verdict strip and **do not produce a
certificate**. Redundancy can then only be reported as *candidates* (clones, smells,
zero-assert tests), never as certified removals.
