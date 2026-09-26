---
name: test-constitution
description: Set up (or amend) a project's test constitution - governance rules agreed up front that keep an agent-driven test suite adequate but lean - test budgets, risk-tiered adequacy by mutation score instead of 100% coverage, marginal-value admission of new tests, the Red-Green-Refactor-Prune TDD cycle, flake quarantine, certified deletion - as TEST-CONSTITUTION.md plus a machine-enforced test-policy.toml, an agent-instructions block in CLAUDE.md/AGENTS.md, and a CI gate. Use this skill whenever the user wants testing rules, standards, a testing policy, guardrails, or governance for humans or agents; says agents write too many or low-value tests and wants that to stop going forward; wants a coverage policy or test budget; or is starting a new project and wants to set testing up right. For measuring an existing suite use test-audit; for planning tests for one feature use test-plan.
---

# test-constitution

Incremental TDD with agents is locally rational and globally ruinous. Each test is
reasonable on its own, but nothing ever asks whether the suite as a whole still pays for
itself. The fix is the one spec-kit applied to design: agree the rules **before** the work,
write them down, and let machines enforce whatever machines can check.

spec-kit's constitution has test-first and integration-first articles, but none about
test *economy*. This constitution adds them: budgets, marginal-value admission, pruning,
and certified deletion.

The deliverable is four files and one CI step:

| File | Role |
|---|---|
| `TEST-CONSTITUTION.md` | 13 articles: the rules, why, and which are gated. Humans read this. |
| `test-policy.toml` | Every number: budgets, risk tiers, admission rules, quarantine, probation. `tmx gate` reads this. |
| managed block in `CLAUDE.md` / `AGENTS.md` | The six rules an agent needs *while writing a test*. |
| `.test-baseline.json` | The ratchet: the accepted suite state. |
| CI: `tmx gate` | Fails the change, and names the article, when a rule is broken. |

## Workflow

1. **Discover.** Read the project:
   - languages, test runner, source and test roots, and CI;
   - the current test count and suite time (run it with JUnit output if cheap);
   - the domain: what can lose money or data, break auth, or harm a user. That is the
     critical tier.
   Check for an existing constitution or policy. If one exists, this is an **amendment**
   (step 6).
2. **Decide the numbers with the user.** Propose defaults, then ask only what you cannot
   infer (`references/tuning.md`):
   - **Critical-tier paths.** Propose them from the domain scan, and confirm with the user.
     This is the one question worth asking.
   - **Rigor profiles** (`references/rigor-profiles.md`). The project default is usually
     R3 Standard, and the critical tier R4 Strict. Offer R5 High-Assurance only for
     safety- or mission-critical components, and say plainly that R5 is not
     certification. Offer R1/R2 for prototypes or internal tooling. The user can name a
     level directly ("set this repo up at Strict").
   - **`max_tests`.** If a `test-audit` exists, use its certified minimum plus 30–50%
     headroom. Otherwise use today's count plus one change's worth of new tests (the
     `adopt.py` default), so a good test for a real gap is not blocked on day one. Then plan an
     audit to ratchet it down.
   - **`max_suite_seconds`.** Aim for a PR tier under 5–10 minutes end to end.
   - **Mutation thresholds per tier.** The defaults are 0.80 critical and 0.60 standard,
     with glue ungated.
   - **Per-change new-test limit.** The default is 8.
3. **Adopt.** First run the suite once with JUnit output. The day-one budget must count
   parametrized rows, which a static count cannot. Then:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/adopt.py --root . --src <src-root> \
     --critical '<glob>' [--critical '<glob>'] --rigor R3 --critical-rigor R4 \
     --junit report.xml [--max-tests N] [--max-seconds S] \
     --agents CLAUDE.md[,AGENTS.md] [--codeowners @org/test-owners]
   ```
   `--codeowners` routes every governance file to a human owner: the constitution, the policy,
   the baseline, the probation and quarantine lists, and the protected and survivor files.
   Pair it with branch protection that requires code-owner review. The gate already judges
   PRs by the base branch's policy, and CODEOWNERS closes the other door, which is merging
   an amendment without a human.
   The script writes the constitution and policy from `assets/`, upserts the managed
   agent block, and git-ignores `.tmx/`. It refuses to overwrite an existing
   constitution without `--force`.

   Then **edit the constitution for this project**:
   - fill in examples for Article I (what counts as a named behavior here);
   - name the architectural boundaries where mocks are allowed (Article VI);
   - list the tiers the CI actually has (Article X).

   Do not dilute the articles to fit current practice. The point is to change practice.
   Record any genuine exception in the amendment log with its reason.
4. **Baseline and gate.**
   - Run the suite with JUnit output, then
     `python3 ${CLAUDE_SKILL_DIR}/../test-audit/scripts/tmx.py baseline --junit <xml>`.
     Use `--matrix` too if a kill matrix exists.
   - Run `tmx gate --policy test-policy.toml --junit <xml>` once locally. On adoption day
     it must pass, since budgets start at today's state. Fix the policy, not the gate, if
     it does not.
   - Hand the CI wiring to `test-ci`, or use the minimal job in `references/ci-snippet.md`.
5. **Optional: an edit-time guard for agents.** Offer to install the project-level Claude
   Code hook from `references/hooks.md`. It runs the smell check on every test file an agent
   writes and feeds violations back immediately. Gates catch at PR time; the hook catches
   at edit time. Ask before writing `.claude/settings.json`.
6. **Amendments.**
   - Change `test-policy.toml` and/or the article text.
   - Append a row to the amendment log (date, version + 1, change, reason).
   - Re-run the gate.
   Raising `max_tests`, lowering a mutation threshold, or removing a gated rule always
   needs a reason that names a real cost.

   With `--base`, the gate judges a PR by the **base branch's** policy and baseline, so a
   change cannot loosen its own gate. An amendment therefore takes effect once it merges.
   Land it as its own PR before the work that needs the new room. "Too many tests fail the gate" is not a reason:
   that is the gate working.
7. **Report.** Say what was adopted, and the numbers chosen and why. Say what is gated and
   what is advisory only. Point out the next step: `test-audit` for an existing suite,
   `test-plan` for new work.

## Principles behind the articles

The full article-by-article rationale, with sources, is in `references/articles.md`. In
short:
- Coverage is a diagnostic, not a target. Mutation score in risk tiers is the adequacy
  measure (Inozemtseva & Holmes; Google's mutation testing; ISO/IEC/IEEE 29119 risk-based
  testing).
- Tests are admitted on marginal value (TestGen-LLM's filters, Meta ACH, JiTTest's
  catching vs hardening split).
- Rules beat instructions. Agents follow gates and hooks more reliably than prose (Claude
  Code best practices; TDAD; machine-readable TDD manifestos).
- Deletion is normal but certified, and reversible first (Shi et al.; Google TAP).

## What not to do

- Don't set `max_tests` below today's count on adoption day. CI would go red for reasons
  unrelated to the change being made. Ratchet down through `test-reduce`.
- Don't gate on global line coverage. It rewards the wrong tests.
- Don't write articles the team will not follow. Mark a rule advisory rather than gating
  a rule that will be bypassed.
- Don't hand-edit the managed block between the `test-skills:constitution` markers.
  Re-run `adopt.py`, which updates it idempotently.

## Reference files

- `references/rigor-profiles.md`: R1–R5, what each level adds, and what the gate enforces
  at each.
- `references/articles.md`: each article's rationale, the sources and standards behind it,
  and how it is enforced.
- `references/tuning.md`: how to choose each number, and when to amend.
- `references/hooks.md`: the edit-time Claude Code hook for test files.
- `references/ci-snippet.md`: the minimal gate job for GitHub Actions and GitLab.
- `assets/TEST-CONSTITUTION.md`, `assets/test-policy.toml`, `assets/agent-block.md`: the
  templates.
