# Probation outside pytest

The list is the same `.test-probation.json`. Only the exclusion mechanism differs.

| Runner | PR tier excludes probation | Nightly includes it |
|---|---|---|
| Jest | generate `jest.probation.json` from the list, then `--testNamePattern` with a negative lookahead, or move demoted `it` blocks into `*.probation.test.ts` and set `testPathIgnorePatterns: ["\\.probation\\."]` | a separate config without the ignore |
| Vitest | `*.probation.test.ts` files plus `exclude` in the PR config | nightly config |
| Go | the build tag `//go:build probation` on moved tests | `go test -tags probation ./...` |
| Cargo | `#[cfg_attr(not(feature = "probation"), ignore)]` | `cargo test --features probation -- --include-ignored` |
| JUnit 5 | `@Tag("probation")`, with `excludeTags` in the PR profile | nightly profile includes it |

Moving demoted tests into dedicated files keeps them out of the way, and makes the final
delete a file deletion.
