---
# yaml-language-server: $schema=../../.lore/schemas/reference.schema.json
type: Reference
title: State of the art in agentic TDD and sustainable test suites
tags:
  - research
  - testing
summary: "September 2026 research on agent test bloat, suite reduction and adequacy, provable coverage, industry standards and CI practice, and how each finding shaped the plugin."
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:09:33.414Z
---

# State of the art in agentic TDD and sustainable test suites

Research carried out on 2026-09-26, across four parallel web-research passes:
- agentic TDD and LLM test generation;
- test-suite reduction and adequacy;
- provable coverage and formal methods;
- industry standards and engineering playbooks.

Each claim cites its source. Items the researchers could not verify against a primary
source are marked *(secondary)* or *(unverified)*. Many 2026 arXiv items are preprints.

## Details

### Conclusions that drive the design

1. **Agents add tests but don't prune them.** Agents touch test files in 23% of commits
   against 13% for humans, and add mocks in 36% of test commits against 26%
   ([Hora & Robbes 2026](https://arxiv.org/abs/2602.00409)). They identify stale tests at
   about 36% F1 ([TEBench 2026](https://arxiv.org/abs/2605.06125)). Their tests barely change
   task outcomes ([Chen et al. 2026](https://arxiv.org/abs/2602.07900)). One team's suite
   almost quadrupled in nine months, adding about 2,000 tests a week
   ([Linear 2026](https://linear.app/now/ci-bottleneck-reworked)).
2. **Exhortation fails; gates work.** What works is filtering tests by measurable gain
   ([TestGen-LLM](https://arxiv.org/abs/2402.09171)), mutation-guided admission
   ([Meta ACH](https://arxiv.org/abs/2501.12862)), ephemeral catching tests
   ([Meta JiTTest](https://arxiv.org/abs/2601.22832)), deterministic manifestos
   ([Hasanli et al. 2026](https://arxiv.org/abs/2604.26615)), and hooks and gates over
   prompts ([Claude Code best practices](https://code.claude.com/docs/en/best-practices)).
3. **Coverage is the wrong reduction criterion; kill sets are the right one.** Only a
   certificate plus a reversible probation stage makes deletion safe. Coverage-based
   reduction lost up to 20.5% of killed mutants, while kill-based reduction lost none
   ([Shi et al. FSE 2014](https://mir.cs.illinois.edu/awshi2/publications/FSE2014.pdf)).
   Real failed builds were still missed at rates up to 52%
   ([Shi et al. ISSTA 2018](https://mir.cs.illinois.edu/marinov/publications/ShiETAL18TSRinReal.pdf)).
4. **"Enough tests" can be a stated, checkable claim.** It needs an explicit input model
   (partitions under a uniformity hypothesis, t-way interaction, a small scope), a trusted
   oracle, and a non-vacuity check (mutation). See Gaudel, NIST, and Jackson below.
5. **Standards already say "adequate, not absolute".** ISO 29119-2 and ISTQB make risk
   decide depth. DO-178C and NASA use coverage as a *check* on requirements-based tests,
   with justified waivers. FDA CSA endorses records commensurate with risk. DORA puts
   trust and speed over test count.
6. **Nobody ships test budgets or proof-subsumed test deletion.** The research passes found
   no mainstream tool for per-PR test budgets and no tool that deletes tests because a proof
   subsumes them. That gap is this plugin's niche.

### 1. The problem: agent-driven test bloat

| Evidence | Finding |
|---|---|
| [Hora & Robbes 2026](https://arxiv.org/abs/2602.00409) (1.2M commits) | Agents touch tests in 23% of commits against 13% for humans. 36% of agent test commits add mocks, against 26%. Agents reach for a generic `mock` 95% of the time. |
| [Chen et al. 2026](https://arxiv.org/abs/2602.07900) (SWE-bench Verified, six LLMs) | Test writing doesn't separate resolved from unresolved tasks. Most agent "tests" are print probes. Prompting for more or fewer tests does not change results. |
| [TEBench 2026](https://arxiv.org/abs/2605.06125) | Identifying which tests need to change peaks at 45.7–49.4% F1. Detecting stale tests is about 36%. Agents' execute-fail-fix loop "structurally cannot address stale or missing tests." |
| [Böckeler, "TDD in the agent loop"](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html) | No clear quality gain from TDD, at 3–8.5× the tokens. Some tests are tautological. Non-TDD runs wrote 58–107 tests. |
| [LLM test smells](https://arxiv.org/abs/2410.10628) (20,505 suites) | Assertion Roulette and Magic Number are pervasive. Redundant Assertion and Lazy Test grow with project size. |
| [LLM oracles](https://arxiv.org/abs/2410.21136); [Canedo 2026](https://arxiv.org/abs/2608.17214) | Generated oracles capture *actual* rather than *expected* behavior. State-anchored oracles cancel faults exactly. |
| [Linear 2026](https://linear.app/now/ci-bottleneck-reworked); [daily.dev](https://daily.dev/posts/reducing-redundant-test-bloat-generated-by-ai-coding-agents-3y4ecbega) | Suites grew about 4× in 2026 (~2,000 tests a week). One team removed 300 tests; its rule is "confirm the code branches on that difference". |
| [DORA 2024](https://dora.dev/research/2024/dora-report/) / [2025](https://dora.dev/dora-report-2025/) | 2024: +25% AI adoption goes with an estimated −7.2% delivery stability. 2025: AI still correlates negatively with stability "without robust control systems, like strong automated testing." |

### 2. What agent tooling does today

- **Claude Code** gives verification criteria and ranks enforcement: prompt, then `/goal`,
  then Stop hook, then verifier subagent. It warns that chasing every reviewer finding
  produces "tests for cases that can't happen."
  ([docs](https://code.claude.com/docs/en/best-practices))
- **GitHub spec-kit** has a constitution with Article III (test-first, non-negotiable) and
  Article IX (integration-first; real DBs over mocks). It has **no** economy articles: no
  budget, redundancy or deletion rules.
  ([spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md))
- **Kiro** turns EARS requirements into Hypothesis properties, where one property replaces
  many examples. Its MVP mode marks tests optional.
  ([PBT](https://kiro.dev/blog/property-based-testing/))
- **OpenAI Codex AGENTS.md** has concrete anti-bloat bans: no tests for static values, no
  negative tests for removed logic, whole-object comparisons.
  ([AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md))
- **Meta JiTTest** generates tests per diff and throws them away, with no maintenance cost.
  Its hardening vs catching split is the basis for our Article IX.
  ([paper](https://arxiv.org/abs/2601.22832),
  [blog](https://engineering.fb.com/2026/02/11/developer-tools/the-death-of-traditional-testing-agentic-development-jit-testing-revival/))
- **TDAD** gives the agent a code-to-test map, and regressions fell from 6.08% to 1.82%.
  Plain TDD instructions without that context *raised* them to 9.94%.
  ([arXiv 2603.17973](https://arxiv.org/abs/2603.17973))
- **Kent Beck** names deleting or disabling tests as the telltale sign of a cheating
  "genie". ([Augmented coding](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes))
- **Anthropic's agentic PBT** ran a Claude Code agent over 100 Python packages. 56% of its
  reports were valid bugs, and 86% of the top-ranked ones.
  ([arXiv 2510.09907](https://arxiv.org/abs/2510.09907)) PBT-Bench measures agent bug
  recall at 42–83%. ([arXiv 2605.15229](https://arxiv.org/abs/2605.15229))

### 3. Adequacy: coverage vs mutation

- **Coverage is a weak proxy.** Once size is controlled for, coverage correlates only
  weakly with effectiveness, and MC/DC adds no insight over statement coverage.
  ([Inozemtseva & Holmes ICSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf))
- **Mutants are a good but imperfect proxy.** 73% of real faults couple to common mutants,
  and 17% couple to none. ([Just et al. FSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/fse_2014_just.pdf))
  Mutation score is a weak *predictor* but good *guidance*: suites selected for it beat
  random suites of the same size.
  ([Papadakis et al. ICSE 2018](https://coinse.github.io/publications/pdfs/Papadakis2018hi.pdf))
- **Google's diff-based mutation** puts at most one mutant per line and skips "arid" lines.
  The share of findings developers rated useful rose from 20% to 80% as those rules were
  refined, and developers who saw mutants wrote better tests.
  ([2018](https://research.google.com/pubs/archive/46584.pdf),
  [2021](https://arxiv.org/abs/2103.07189))
- **Pseudo-tested methods** are covered methods where no test fails when the body is
  removed: 6–53% of methods ([Niedermayr](https://arxiv.org/abs/1611.07163)) and 1–46%
  ([Vera-Pérez](https://arxiv.org/pdf/1807.05030)). Extreme mutation is the cheap first
  pass.
- **Adequate coverage numbers.** Google treats 60/75/90% as acceptable/commendable/
  exemplary, says project-wide goals above 90% are not worth it, and puts a 90% floor on
  per-commit coverage.
  ([Google Testing Blog 2020](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html))
  NIST IR 8397 sets a minimum of 80% statement coverage but says "very high code coverage
  guarantees little", and that data-flow and mutation are stronger.
  ([NIST IR 8397](https://nvlpubs.nist.gov/nistpubs/ir/2021/NIST.IR.8397.pdf))
- **Mutation is on the Thoughtworks Radar at Trial**: "the most honest signal."
  ([Radar](https://www.thoughtworks.com/radar/techniques/mutation-testing)) AWS
  Well-Architected lists "over indexing on coverage metrics" as an anti-pattern.
  ([AWS](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-functional-testing.html))

### 4. Reduction, selection and prioritization

- **The formulation.** Minimization is a minimal hitting set, which is NP-complete. The
  standard toolkit is greedy, HGS, ILP and multi-objective optimization.
  ([Yoo & Harman 2012](http://www0.cs.ucl.ac.uk/staff/m.harman/stvr-shin-survey.pdf))
- **The evidence is contested.**
  - Early studies found 1.45% loss.
  - Rothermel found more than 50% loss in over half of the suites.
  - Shi et al. 2014: kill-set reduction loses no kills, and keeping 95% of kills buys
    17 percentage points more reduction.
  - Shi et al. 2018: up to 52.2% of *real* failed builds were missed even when mutant loss
    was 2–3%, although an oracle could have kept only about 20% of tests.
- **Selection, not deletion, is what scales.**
  - **Google TAP:** 91.3% of test targets never failed, and 1.23% ever caught a
    breakage.
    ([ICSE-SEIP 2017](https://huang.isis.vanderbilt.edu/cs8395/paper/google-testing-icse-seip-17.pdf))
  - **Meta Predictive Test Selection:** half the infrastructure cost, while catching more
    than 99.9% of faulty changes. ([arXiv 1810.05286](https://arxiv.org/abs/1810.05286))
  - **Shopify:** selection with 99.94% failing-test recall.
    ([blog](https://shopify.engineering/spark-joy-by-running-fewer-tests))
  - **Test impact analysis.**
    ([Fowler](https://martinfowler.com/articles/rise-test-impact-analysis.html))
- **Mutant subsumption and minimal mutant sets.**
  ([Ammann et al. ICST 2014](https://www.albany.edu/faculty/offutt/research/papers/MiniMutant-ICST2014.pdf))
  Even perfect mutant reduction beats random sampling by only about 13%.
  ([Gopinath ICSE 2016](https://agroce.github.io/icse16.pdf))

### 5. Provable coverage: partitions, combinatorics, properties, proofs

- **Complete test sets under hypotheses.**
  - Goodenough & Gerhart (1975) showed that a reliable, valid criterion demonstrates the
    absence of errors, and that coverage alone is not reliable.
    ([ACM](https://dl.acm.org/doi/10.1145/800027.808473))
  - Gaudel's exhaustive test sets, under *uniformity* and *regularity* hypotheses, make
    "passing = satisfying the spec" a theorem.
    ([Springer](https://link.springer.com/chapter/10.1007/3-540-59293-8_188))
  - Category-partition. ([Ostrand & Balcer 1988](https://dl.acm.org/doi/10.1145/62959.62964))
- **Combinatorial interaction.** NIST's rule: most faults involve 1–2 parameters, and none
  has been observed involving more than 6. Full t-way coverage is "in some sense
  equivalent to exhaustive testing."
  ([NIST](https://csrc.nist.rip/Projects/automated-combinatorial-testing-for-software/combinatorial-methods-in-testing/interactions-involved-in-software-failures),
  [SP 800-142](https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-142.pdf))
- **Small-scope hypothesis and bounded-exhaustive testing.**
  ([Andoni, Marinov et al.](https://users.ece.utexas.edu/~khurshid/papers/BET.pdf))
  MongoDB turned a TLA+ model into 4,913 generated tests with 100% branch coverage,
  against 21% for handwritten tests and 92% for AFL.
  ([MongoDB](https://www.mongodb.com/company/blog/engineering/conformance-checking-at-mongodb-testing-our-code-matches-our-tla-specs))
- **Property-based testing.**
  - A PBT kills about 50× more mutants than an average unit test. PBTs are 1.6% of tests
    but kill 15.3% of mutants, and 76% of a PBT's kills come within the first 20 inputs.
    ([OOPSLA 2025](https://cseweb.ucsd.edu/~mcoblenz/assets/pdf/OOPSLA_2025_PBT.pdf))
  - Practice at Jane Street. ([ICSE 2024](https://harrisongoldste.in/papers/icse24-pbt-in-practice.pdf))
  - Generalizing unit tests into properties (Teralizer) gives only small gains on mature
    suites. ([arXiv 2512.14475](https://arxiv.org/abs/2512.14475))
- **Formal verification pairs with conformance testing; it does not replace it.**
  - AWS's IAM authorization engine was written in Dafny and shadow-tested against 10^15
    production samples.
    ([ICSE 2025](https://www.amazon.science/publications/formally-verified-cloud-scale-authorization))
  - Cedar pairs Lean proofs (about 3 minutes to check) with about 100M nightly differential
    tests. ([arXiv 2407.01688](https://arxiv.org/pdf/2407.01688))
  - Kani runs 16,000+ harnesses per change in Rust std.
    ([arXiv 2607.01504](https://arxiv.org/abs/2607.01504))
  - AWS systems-correctness portfolio.
    ([CACM 2025](https://dl.acm.org/doi/10.1145/3729175))
- **Specs are the new bottleneck, and specs need mutation too.**
  - IronSpec found 10 spec bugs. ([OSDI 2024](https://www.usenix.org/system/files/osdi24-goldweber.pdf))
  - Vericoding success is 82% for Dafny and 27% for Lean.
    ([arXiv 2509.22908](https://arxiv.org/abs/2509.22908))
  - Kleppmann: AI will make formal verification mainstream.
    ([blog](https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html))
  - FVSpec translates PBTs into Lean obligations. ([arXiv 2606.01008](https://arxiv.org/abs/2606.01008))
- **Statistical confidence.**
  - Rule of three: n failure-free random tests put about 3/n as the 95% upper bound on
    failure probability.
  - Hard limits on demonstrating ultra-high reliability.
    ([Butler & Finelli](https://shemesh.larc.nasa.gov/fm/papers/Butler-nonq-paper.pdf))
  - Good-Turing residual risk for generative testing.
    ([Böhme FSE 2021](https://mboehme.github.io/paper/FSE21.pdf))

### 6. Industry standards and best-practice frameworks

| Standard / framework | What it says that matters here |
|---|---|
| **ISO/IEC/IEEE 29119-2:2021** | Risk-based by design: activities and resources are "consciously based on… analysed risk". Covers scripted and unscripted testing. ([sample](https://cdn.standards.iteh.ai/samples/79428/67463a92e52c4b5da67536f7143dd25a/ISO-IEC-IEEE-29119-2-2021.pdf)) |
| **ISO/IEC/IEEE 29119-4:2021** | Techniques (EP, BVA, combinatorial, decision table, state transition, metamorphic, MC/DC…) each carry a coverage measure. Projects "will not need to use all", and tailored conformance requires justification. ([sample](https://cdn.standards.iteh.ai/samples/79430/6c93dfe4a05b46a8895e04dfd74ddd24/ISO-IEC-IEEE-29119-4-2021.pdf)) The context-driven community's "Stop 29119" criticism warns against documentation over testing. ([Kaner](https://context-driven-testing.com/please-sign-the-petition-to-stop-iso-29119/)) |
| **ISTQB CTFL v4.0** | "Exhaustive testing is impossible"; "Tests wear out" (formerly the pesticide paradox); risk "may influence the thoroughness and scope"; traceability to risks gives residual risk; regression suites "increase with each iteration", so use impact analysis. ([syllabus](https://astqb.org/assets/documents/ISTQB_CTFL_Syllabus-v4.0.pdf)) |
| **ISTQB CTAL-TA v4.0 / CTAL-TAE v2.0** | The analyst must "balance the need for coverage with a manageable size of the test suite". Move unreliable tests out of the active suite. Removing duplicates cuts time. ([TA](https://astqb.org/assets/documents/ISTQB-CTAL-TA-Syllabus-v4.0-EN-4.pdf), [TAE](https://www.gasq.org/files/content/ISTQB2/ISTQB_CTAL-TAE_Syllabus_v2.0.pdf)) |
| **DO-178C** | Structural coverage *on requirements-based tests*: statement at C, adding decision at B and MC/DC at A. "The purpose of testing is… not to achieve structural coverage". Gaps are resolved by adding a test, fixing the requirement, removing dead code, or justifying. Objectives with independence: A 30, B 18, C 5, D 2. ([AdaCore](https://learn.adacore.com/booklets/adacore-technologies-for-airborne-software/chapters/analysis.html)) |
| **ISO 26262-6** | Unit coverage recommendations by ASIL, with MC/DC highly recommended at D and requirements-based testing highly recommended everywhere. *(secondary: [Coco](https://doc.qt.io/coco/code-coverage-analysis.html))* |
| **IEC 61508-3** | Entry points at all SILs. Branch coverage highly recommended at SIL 3–4, MC/DC at SIL 4. *(secondary)* |
| **IEC 62304** | Classes A/B/C scale by harm, with no mandated coverage percentage. Edition 2 moves to two "process rigor levels". *(secondary)* |
| **NASA NPR 7150.2D / STD-8739.8B** | SWE-219 requires 100% MC/DC for *identified* safety-critical components, with a rationale or risk-based deviation approved by the TA. SWE-052 requires bidirectional traceability, including to hazards (Classes A–C). IV&V independence is technical, managerial and financial. ([NPR](https://nodis3.gsfc.nasa.gov/displayDir.cfm?Internal_ID=N_PR_7150_002D_&page_name=Chapter3), [SWE-219](https://swehb.nasa.gov/display/SWEHBVD/SWE-219+-+Code+Coverage+for+Safety+Critical+Software), [STD-8739.8B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/0/NASA-STD-87398-Revision-B.pdf)) |
| **FDA CSA (final, 2025-09-24)** | Risk-based and least-burdensome. Scripted testing for high process risk, unscripted for lower. Records "commensurate with risk"; CI logs are acceptable evidence. ([FDA](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/computer-software-assurance-production-and-quality-system-software)) |
| **NIST** | "Assurance" is grounds for justified confidence that a claim is achieved. An assurance case is a reasoned, auditable artifact with evidence and explicit assumptions. ([assurance](https://csrc.nist.gov/glossary/term/assurance), [assurance case](https://csrc.nist.gov/glossary/term/assurance_case)) |
| **DORA** | "Don't tolerate flaky tests". Feedback in under 10 minutes. "Ten tests that are reliable, fast, and trustworthy" beat hundreds nobody trusts. ([test automation](https://dora.dev/capabilities/test-automation/), [CI](https://dora.dev/capabilities/continuous-integration/)) |
| **TMMi** | Level 2: test policy and strategy with product risk. Level 4: measurement. Level 5: quality control and test process optimization. ([TMMi](https://www.tmmi.org/tmmi-model/)) |
| **Google SWE book** | Test sizes are separate from scope, with a rough 80/15/5 mix. Flakiness near 1% destroys value; Google runs at about 0.15%. Change-detector tests have negative value. ([ch. 11](https://abseil.io/resources/swe-book/html/ch11.html), [TotT](https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html)) |
| **GitLab / Uber** | GitLab: fast quarantine for 3 days at most, long quarantine for 3 months at most, then automatic deletion, with owners acknowledging within 48 hours. Uber: new → stable → unstable → disabled → deleted. ([GitLab](https://handbook.gitlab.com/handbook/engineering/testing/quarantine-process/), [Uber](https://www.uber.com/us/en/blog/flaky-tests-overhaul/)) |
| **Mutation tools** | Stryker defaults to thresholds of 80/60 with no break score. cargo-mutants recommends `--in-diff` in PRs. No tool recommends a universal score. ([Stryker](https://stryker-mutator.io/docs/stryker-js/configuration/), [cargo-mutants](https://mutants.rs/ci.html)) |
| **Test design canon** | Kent Beck's Test Desiderata ([site](https://testdesiderata.com/)); Khorikov's four pillars, where resistance to refactoring is effectively binary; the Practical Test Pyramid: "push tests as far down as possible" ([Vocke](https://martinfowler.com/articles/practical-test-pyramid.html)). |

### 7. CI scalability practice

- **Budgets.** Aim for a build of about 10 minutes
  ([Fowler](https://martinfowler.com/articles/continuousIntegration.html),
  [DORA](https://dora.dev/capabilities/continuous-integration/)). Google presubmit takes
  about 11 minutes, and passing it predicts post-submit success at 95% or better
  ([ch. 23](https://abseil.io/resources/swe-book/html/ch23.html)). Shopify targets a p95
  under 10 minutes.
- **Tiers.** Presubmit is fast and hermetic; post-submit or nightly carries the rest.
  Bazel timeouts are tied to test size.
- **Flakes.** Quarantine immediately and cap the quarantine's size and age
  ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)). Flake causes: 45% async
  wait, 20% concurrency, 12% order dependency
  ([Luo et al. 2014](https://mir.cs.illinois.edu/marinov/publications/LuoETAL14FlakyTestsAnalysis.pdf)).
- **Deletion.** No industry-wide policy exists. Change detectors should be rewritten or
  deleted, and practitioners argue that deletion by agents should be a privileged,
  separately reviewed change.

### 8. Review of proof-skills and the reuse decision

proof-skills v0.1.1 has four skills: `formal-verify`, `tlaplus-model`, `lean-model` and
`proof-simplify`. It already provides:
- scoped TLA+ and Lean modelling;
- property harvesting and freezing;
- a model ↔ code correspondence;
- reproducing counterexamples in real code;
- the three-config sanity pattern, where every model must be able to fail;
- a Lean trust audit;
- differential testing against Lean executable models (Cedar-style);
- CI tiers for models;
- `proof-simplify`, which turns proven facts into *code* deletions.

**Decision (ADR-0006): use it as-is.** This plugin adds the missing mirror image, turning
proven or exhaustively checked facts into *test* deletions. That work goes in
`coverage-proof`. Its principles carry over directly:

| Principle | proof-skills version | test-skills version |
|---|---|---|
| Must be able to fail | three-config sanity per model | mutation: every retained test and property must kill something; the gate forbids tautologies |
| Evidence for every claim | logs under `formal/<concern>/evidence/` | `.tmx/` matrices, plans, verify and compare logs |
| Frozen criteria | frozen `Properties.tla` | the mutant set, protected list and `--lines` choice are fixed between audit and final compare |
| Bounds stated | "no counterexample within bounds" | "all kills of this mutant scope"; "complete under this partition hypothesis at t-way" |
| Prove before deleting | re-check, refinement or `reach_iff` before a code deletion | certificate, compare and probation before a test deletion |

### 9. How the findings shaped the plugin

| Finding | Design response |
|---|---|
| Agents don't prune; exhortation fails | Article IX adds a Prune step. The gate enforces Articles II–VI and XI. There is an edit-time hook and a managed agent block (ADR-0004). |
| Kill sets beat coverage for reduction | `tmx analyze` does set cover over the kill matrix, with a certificate and independent `verify` (ADR-0002). |
| Real-world loss despite a certificate (Shi 2018) | Demote before delete, with a probation tier and promote-back (ADR-0003). History mutants come from reverted fixes. |
| 17% of real faults couple to no mutant | `--history N` adds real past bugs to the obligations. |
| Extreme mutation and Google sampling are cheap | `--operators extreme` and `--per-line 1`. |
| Keeping 95% of kills buys much more reduction | The trade-off `curve` in every plan; the user chooses, and the report says so. |
| PBT kills about 50× more per test; one property replaces many examples | Article VII. `test-plan` and `test-reduce` prefer properties with spec-anchored oracles. |
| Partition, uniformity and t-way make "enough" checkable | `tmx covering` checks and generates t-way covering arrays over declared partition models. |
| Proofs pair with conformance tests | Article VIII: retire examples inside a proven scope and keep one conformance test (ADR-0006). |
| Standards grade rigor by consequence, and coverage checks requirements-based tests | [Engineering rigor profiles](../specs/engineering-rigor-profiles.md), R1–R5. |
| DORA: fast, trusted, flake-free | PR-tier time budget, flake quarantine window, and no retries-to-green. |
| Agent tests over-mock and anchor to actual behavior | Smells for `mock-heavy`, `implementation-coupled` and `tautology`. Article IV requires spec-anchored oracles. |

### 10. Open gaps and risks

- The mutation operators are a proxy. Certificates are only as strong as the operator set,
  which is why they are paired with probation and history mutants.
- Per-test kill attribution is native for pytest, Stryker and PIT only. Rust and Go need
  adapters.
- MC/DC is not measured by `tmx`. At R5 the project's qualified tool supplies it.
- Equivalent mutants still need human or agent triage. LLM equivalence detection reaches
  about 0.95 precision after pre-processing (Meta ACH), which is a possible future
  assistant.
