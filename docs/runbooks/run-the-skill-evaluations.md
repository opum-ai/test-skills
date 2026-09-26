---
# yaml-language-server: $schema=../../.lore/schemas/runbook.schema.json
type: Runbook
title: Run the skill evaluations
tags:
  - evals
summary: Build workspaces, run with/without-skill agents, grade objectively with grade.py and blind assertion graders, and run the trigger suite with claude plugin eval.
generated:
  by: lore/0.9.2
  at: 2026-09-26T14:53:54.621Z
---

# Run the skill evaluations

## Purpose

Measure whether the skills change outcomes, with graders that never trust an agent's own
claims. There are two suites:
- **Benchmark.** Four task cases (`evals/evals.json`), each run with and without the
  skills, then graded two ways:
  - objectively, by `evals/grade.py`;
  - by blind assertion graders.
- **Trigger suite.** 48 queries (`evals/triggers.py`), run through `claude plugin eval`.
  Each skill gets 5 should-fire queries and 3 near misses.

## Prerequisites

- A Python with `pytest`, `coverage` and `hypothesis`, for example
  `uv venv && uv pip install pytest coverage hypothesis`. Pass it as `--python`.
- `git`. Fixture workspaces get a real history: `make_history.sh` creates the shop fixture's
  three bug-fix commits, which become history mutants.
- The trigger suite costs about $13 per run at 1 run per case.

## Steps

1. **Build the workspaces.** For each case and arm:
   `evals/setup_ws.sh <fixture> <dir>/<case>/<with|without>/ws`
2. **Run the agents.** Give each one the case prompt from `evals/evals.json` and the
   pinned Python.
   - With-skill arms also get the skills directory and the six skill descriptions.
   - Baseline arms are told to stay inside the workspace.
   - Save each agent's final message as `FINAL.md`.
3. **Grade objectively:**
   `python3 evals/grade.py <case> <ws> --python <py> > grade.json`
   - `shop-reduce`: grafts the agent's tests onto a pristine copy of the fixture history,
     re-collects the kill matrix on the PR tier (excluding probation, quarantine and slow
     tests) with `--history 5`, and reports lost kills and how many of the three
     historical bugs are still caught.
   - `loyalty-greenfield`: runs `evals/hidden/test_loyalty_acceptance.py`, 43 tests the
     agent never saw. They pass 43/43 on `evals/hidden/loyalty_reference`. It also reports
     tests added and the mutation score of the agent's suite on the new code.
   - `shop-audit` and `constitution-setup`: check that the source is unchanged, count
     tests, and inspect the CI and agent-instruction files.
4. **Grade blind.** Copy each case's two workspaces to `A`/`B` under a random mapping, and
   give one grader agent the case's assertions, both final messages, and the objective
   metrics, all labelled A/B. It returns PASS/FAIL per assertion with evidence. Unblind
   afterwards.
5. **Run the `claude plugin eval` suites** with `evals/run_plugin_eval.sh [trigger|task|all]`.
   Extra arguments pass through, for example `--runs 3` or `--case 'task-shop-*'`.
   - **Before the run,** the script regenerates `evals/cases` from `evals/evals.json` and
     `evals/triggers.py`. It installs the TypeScript fixture's `node_modules` if they are
     missing.
   - **Python.** The project environment is `.venv`, which is git-ignored.
     `evals/setup_env.sh` builds it with uv from the pinned `evals/requirements.txt`, and the
     runner calls that script itself on first use. Set `EVAL_PYTHON` to use another
     interpreter instead. Either way, it goes first on `PATH` for the agents.
   - **Where the output goes.** Each invocation writes to
     `/tmp/test-skills-plugin-eval/<timestamp>/`, with `latest` symlinked to it. `LOG_ROOT`
     overrides the location. The directory holds:
     - `run.env`: what was run;
     - `<suite>.log`: the live console, recorded through `script(1)`;
     - `<suite>.debug.log`: a per-message trace, which serves as a heartbeat;
     - `<suite>.json` and `<suite>.html`: the full results and the report;
     - `status`: one line per suite;
     - `DONE`: written last.
   - **Monitoring.** Another session can watch `status` and the trace's growth, then review
     the JSON once `DONE` appears.
   - **Task agents run in plugin eval's OS sandbox, which cannot be configured.** Inside it:
     - Bash, Write and Edit need an operator grant, so the runner passes
       `--allow-tools Bash Write Edit`. Without it, every agent is read-only and the scores mean
       nothing (the first run, 2026-09-26, was invalid for this reason).
     - The run's own home replaces yours, and your real home is unreadable.
     - Executables outside the run are denied, including `/tmp`, `/Volumes` and a uv venv
       whose interpreter lives in `~/.local`.
     - The `/usr/bin` xcrun shims (`git`, `python3`) fail on an unwritable cache.

     `evals/eval_toolchain.sh` therefore builds a relocatable CPython with the pinned deps at
     `/tmp/test-skills-toolchain`, once per requirements change. Each task scaffold then
     calls `evals/stage_toolchain.sh`, which runs outside the sandbox. That script:
     - clones the toolchain into the run's home as `.tc/`;
     - adds wrappers for `python`, `git` (a real binary), and `npm`/`npx` (npm copied out of
       nvm);
     - prepends them to `PATH` through the run home's `.zshenv`.
     The workspace itself is untouched.
   - **Stryker in the sandbox.** Stryker's parent process opens a TCP log server for its workers,
     and the sandbox denies every `listen()`, TCP and Unix alike. The ts-audit scaffold runs
     `evals/sandbox_patch_stryker.cjs` on the run's own copy of `node_modules`. The patch makes
     the log server a no-op and fails loudly if Stryker's code changes. Mutation results are
     unchanged: 77 mutants, 75 killed, 57 with several killers, inside and outside the sandbox.
   - **Grading in two layers.** plugin eval's LLM graders read only what the agent produced, so:
     - assertions that cite grader-held evidence become checks on the report's claims;
     - "did not modify" and the hidden acceptance tests are left to the objective layer (the
       `JUDGE` map in `make_cases.py`).
     The runner passes `--keep-temp`, then `evals/grade_plugin_eval.py` runs `grade.py` on every
     kept workspace. That layer covers the hidden tests, re-collected kill matrices and
     tree-hash "unchanged" checks. It writes `task-objective.{json,md}` beside the eval result.
   - **Model.** The agent model is pinned with `--model` (`EVAL_MODEL`, default
     `claude-opus-5-5`). Without it, a run uses the child session's default model.
   - **Arms.** Trigger cases run without a baseline arm. Task cases run with and without the
     plugin. Reports stay local unless you pass `--publish-report`.
   A run that hits `max_turns` after loading the skill counts as a genuine pass. So does a
   near miss that used all its turns without loading the skill.
6. **Record the results** in [Skill evaluation suite](../stories/skill-evaluation-suite.md),
   with the date and model.

## Rollback

Nothing to roll back. Workspaces live in a scratch directory; delete it when done.
`evals/results/` is git-ignored.
