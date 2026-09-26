# test-skills

**Sustainable test suites for agentic engineering.** Six Claude Code skills that stop
agent-driven development from burying a project under its own tests, and dig existing
projects out:
- they set the rules of test economy **up front**, as a constitution that CI enforces;
- they plan the **smallest adequate** test set for new work;
- they **measure** existing suites with per-test mutation kill matrices;
- they **cut** them down with machine-checked certificates that no fault detection was lost.

**Status:** v0.1.0. Owned by [Opum AI](https://github.com/opum-ai), MIT licensed. It is a
companion to [proof-skills](https://github.com/opum-ai/proof-skills).

## Why

Coding agents add tests on every change and almost never remove them:
- agents touch test files in 23% of commits, against 13% for humans;
- they detect stale tests at about 36% F1;
- a medium project reaches thousands of tests;
- CI slows, flakes, and breaks on every refactor;
- the extra tests catch little that the core ones don't.

The research (see [State of the art](docs/reference/state-of-the-art-in-agentic-tdd-and-sustainable-test-suites.md))
points to **gates, not exhortation**. Keep a new test only if it adds measurable value.
Reduce by mutation kill sets, not coverage. Demote before you delete. Where a rule can be
stated, write it once as a property or a proof.

## The skills

| Skill | Role |
|---|---|
| **`test-constitution`** | Governance up front. TEST-CONSTITUTION.md (13 articles), test-policy.toml (every checkable number), an agent-instructions block, an optional edit-time hook, and a CI gate. |
| **`test-plan`** | New work. Behaviors → partition models → properties and tables → a budget, then TDD as **Red → Green → Refactor → Prune**. |
| **`test-audit`** | Existing suites. A kill matrix, a certified minimal subset, redundancy reasons, clone clusters, smells, a CI review, and constitution compliance. Reports only; changes nothing. |
| **`test-reduce`** | Cutting. Consolidate into tables and properties, **demote to probation**, delete after the window, and prove zero lost kills at every stage. |
| **`test-ci`** | Pipelines. PR/main/nightly tiers under a time budget, quarantine instead of retries, the gate, mutation on the diff, and probation runs. |
| **`coverage-proof`** | Math. Kill-set certificates, t-way covering arrays under a stated hypothesis, property subsumption, bounded-exhaustive checks, statistical bounds, and TLA+/Lean via proof-skills. |

### Rigor profiles

Every skill works at a selectable **rigor level**:

| | Profile | For |
|---|---|---|
| R1 | Minimal | spikes and experiments |
| R2 | Lightweight | small, reversible changes |
| **R3** | **Standard** (default) | routine production work |
| R4 | Strict | money, security, and hard-to-reverse changes |
| R5 | High-Assurance | safety- or mission-critical components |

Higher rigor means **stronger evidence, not more tests**: survivor triage, properties,
proofs, traceability, independent review, and human approval that no agent can supply.

A change is held to the highest level of anything it touches. R5 is not certification. See
the [rigor profiles spec](docs/specs/engineering-rigor-profiles.md).

## The engine: `tmx`

`skills/test-audit/scripts/tmx.py` is stdlib-only Python 3.9+. It is vendorable into any CI.

```text
collect-pytest   per-test coverage + kill matrix: AST mutants (incl. money literals, rounding modes, raise
                 deletion, min/max/sum swaps) run against covering tests in throwaway copies, survival
                 confirmed on the full suite, hangs attributed; control run must be green;
                 --history N adds real past bugs; --extra-mutants adds domain faults
import-stryker   JS/TS/C#/Scala kill matrices        import-pit   Java/Kotlin kill matrices
analyze          minimal kill-preserving subset (set cover, exact B&B + bound) + certificate + curve
verify [--rerun] independent certificate check; --rerun replays each mutant against the retained suite
compare          lost obligations between matrices (unique mutant keys)
subsumes         does a property kill everything a cluster of examples killed?
smells / clones  static smells tagged by article; copy-paste clusters -> tables/properties
covering         t-way covering arrays over declared partition models
probation        demote-before-delete lifecycle      baseline / gate   the constitution in CI
```

## Install

```text
/plugin marketplace add opum-ai/opum-marketplace
/plugin install test-skills@opum
```

`collect-pytest` needs `pytest` and `coverage` in the target project's environment. Nothing
else is installed. Other languages come in through Stryker or PIT reports, or through JUnit
XML for counts and time.

## Usage

```text
> Our test suite has gotten out of hand; every refactor breaks dozens of tests. How many do we actually need?
> Cut the suite down radically without losing real protection.
> Set up testing governance so agents stop piling on tests. Strict for billing.
> Implement SPEC.md test-first, and keep the test suite sustainable.
> Prove these 40 tests for parse_duration are enough, or show which can go.
```

## Evaluation

See [Skill evaluation suite](docs/stories/skill-evaluation-suite.md) for the method and the
full results. Graders never trust the agent's own claims:
- they re-run the suite;
- they re-collect kill matrices and compare them against a pristine copy;
- they check that the three real historical bugs are still caught;
- they run hidden acceptance tests the agent never saw.

Iteration 1 of the skill-creator benchmark (2026-09-26, claude-opus-5-5): 5 cases, 3 runs per
arm, assertion graders plus objective grading. Assertion pass rate was **96% ± 6% with the skills vs 87% ±
11% without**, at +36% tokens and +20% time.

| Case | With skills | Without | Objective difference |
|---|---|---|---|
| Reduce a bloated suite (172 tests) | **8/8 ×3** | 5, 7, 7 | PR tier **49–57** vs 97–109 items; **0 lost kills** in every skill run, while a baseline lost a tax-rate kill |
| Audit a bloated suite | **13/13 ×3** | 12, 11, 12 | domain faults and reversible staging only with the skills |
| Implement a spec test-first | **6/7 ×3** | 5, 5, 6 | 43/43 hidden tests in all runs; 34–41 vs 36–52 cases added; no smells vs ≥1 |
| Set up test governance | **8, 7, 8** | 7, 7, 8 | one skill run was red on day one for money files; now a required check |
| Audit a TypeScript suite (Stryker) | 9, 9, 8 | 9, 9, 8 | no difference; this case needs a hidden fault set |

Earlier single-run blind A/B comparison (same day):

| Case | With skills | Without | What differed |
|---|---|---|---|
| Reduce a bloated suite (172 tests) | **8** | 6.5 | PR tier **44** vs 79 at **0 lost** of 274 kills in both (expanded operators neither used); reversible probation; found and closed a money blind spot |
| Implement a spec test-first | **8** | 7 | both 43/43 on hidden acceptance tests; **33 vs 66** tests added; mutation **98.7% vs 95.3%** |
| Set up test governance | **8** | 6 | only the skill run's gate resisted a PR loosening its own policy; mutation-based admission; quarantine |
| Audit a bloated suite | 8 | **9** | both excellent; the baseline re-ran its reduced suite. That gap is now closed by `verify --rerun` |
| **Mean** | **8.0** | 7.1 | assertions 32/33 vs 29/33; the skills cost ~1.3–2× the time and tokens |

The trigger suite scored 48/48, with 5 should-fire queries and 3 near misses per skill. An
adversarial engine review found 12 defects, all fixed. Each fix has a regression test that
fails on the pre-fix engine.

## Repository layout

```
.claude-plugin/plugin.json     plugin manifest (the repo root is the plugin root)
skills/<skill>/                SKILL.md, references/, assets/, scripts/
skills/test-audit/scripts/     tmx engine (stdlib) + pytest plugin
tests/                         the engine's own suite (~57 tests; ~10 s fast, ~60 s with soundness), under its own constitution
evals/                         fixtures, objective graders, hidden acceptance tests, trigger sets
docs/                          OKF bundle: epic, stories, ADRs, rigor spec, research reference
```

## Development

```bash
python -m pytest -q tests                        # engine suite (needs pytest, coverage, hypothesis)
python3 evals/make_cases.py                      # regenerate claude plugin eval cases
claude plugin eval . --tag trigger --scaffold --ablation none -j 8 --threshold 0
python3 evals/grade.py <case> <workspace> --python <py>   # objective grading of a run
claude plugin validate . && lore check
```

Track work with `quest`, and write docs with `lore` (see CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
