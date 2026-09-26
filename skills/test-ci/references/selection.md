# Affected-test selection

| Ecosystem | Tool | Notes |
|---|---|---|
| Nx / Turborepo | `nx affected -t test`, `turbo --filter=...[origin/main]` | project-graph based |
| Bazel / Buck / Pants | `bazel query 'rdeps(//..., set($(changed)))'` | Google TAP style |
| Python | `pytest-testmon`, or the tmx matrix coverage map (tests covering changed lines) | file- or line-level dependencies |
| JS | Jest `--changedSince=origin/main`, Vitest `--changed` | module graph |
| Go | `go list -deps` reverse mapping per package | package level |
| Predictive | Launchable / Develocity / Meta-style ML | confidence curves |

Keep selection honest:
1. **Run the full suite on main** (post-merge). Selection misses are then caught within
   minutes.
2. **Treat untraceable changes as "run everything"**: config, lockfiles, fixtures, SQL,
   and CI files (Shopify, Hammant).
3. **Measure recall.** On main runs, record whether any failing test would have been
   deselected on its PR. Shopify reported 99.94% recall.
