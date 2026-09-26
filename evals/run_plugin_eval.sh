#!/usr/bin/env bash
# Run the plugin's `claude plugin eval` suites with everything written to one log directory,
# so another session can watch the run and review it afterwards.
#
#   evals/run_plugin_eval.sh [trigger|task|all] [extra claude plugin eval args...]
#
#   evals/run_plugin_eval.sh trigger                  # 48 trigger cases, no baseline arm
#   evals/run_plugin_eval.sh task --runs 3            # 5 task cases, with and without the plugin
#   evals/run_plugin_eval.sh task --case 'task-shop-*'
#
# Output (LOG_ROOT defaults to /tmp/test-skills-plugin-eval):
#   $LOG_ROOT/<timestamp>/            one directory per invocation; $LOG_ROOT/latest points at it
#     run.env                         what was run: suites, args, git SHA, python, node
#     <suite>.log                     the live console display, recorded as it runs (ANSI; read with
#                                     sed 's/\x1b\[[0-9;?]*[A-Za-z]//g')
#     <suite>.debug.log               per-message trace events: a heartbeat while agents work
#     <suite>.json                    the full result (per-run scores, grader verdicts)
#     <suite>.html                    the HTML report
#     <suite>/                        claude plugin eval's aggregate-result.json
#     task-objective.{json,md}        grade.py on every kept task workspace (hidden tests, kill matrices)
#     status                          one line per suite: "<suite> running|exit=<code>"
#     DONE                            written last; its presence means the whole run finished
#
# Python: the project's .venv (created with uv by evals/setup_env.sh on first use), or set
# EVAL_PYTHON to another interpreter with pytest, coverage and hypothesis. Its bin directory
# is put first on PATH for the agents.
# The agent model is pinned to EVAL_MODEL (default claude-opus-5-5); graders use plugin eval's judge.
# The report is kept local (--no-publish) unless you pass --publish-report.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
SUITE="${1:-all}"; shift || true
case "$SUITE" in trigger|task) SUITES=("$SUITE") ;; all) SUITES=(trigger task) ;;
  *) echo "usage: $0 [trigger|task|all] [claude plugin eval args...]" >&2; exit 64 ;; esac

LOG_ROOT="${LOG_ROOT:-/tmp/test-skills-plugin-eval}"
DIR="$LOG_ROOT/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DIR" && ln -sfn "$DIR" "$LOG_ROOT/latest"

# The project env (.venv, built by evals/setup_env.sh with uv) is the default; it is created on first use.
if [[ -z "${EVAL_PYTHON:-}" ]]; then
  "$ROOT/evals/setup_env.sh" || exit 1
  EVAL_PYTHON="$ROOT/.venv/bin/python"
fi
PY="$EVAL_PYTHON"
if ! "$PY" -c "import pytest, coverage, hypothesis" 2>/dev/null; then
  echo "EVAL_PYTHON=$PY lacks pytest/coverage/hypothesis; the Python task cases need them." >&2
  [[ " ${SUITES[*]} " == *" task "* ]] && exit 1
fi
PYBIN="$(dirname "$(command -v "$PY")")"; export PATH="$PYBIN:$PATH"

# Task agents run inside plugin eval's OS sandbox, which can't use your installed toolchains;
# build the one each case's scaffold stages into the run (see evals/eval_toolchain.sh).
if [[ " ${SUITES[*]} " == *" task "* ]]; then
  "$ROOT/evals/eval_toolchain.sh" >/dev/null || { echo "eval toolchain build failed" >&2; exit 1; }
fi

# The TypeScript case copies the fixture's node_modules (git-ignored) into its workspace.
if [[ " ${SUITES[*]} " == *" task "* && ! -d "$ROOT/evals/fixtures/ts-bloated-cart/node_modules" ]]; then
  (cd "$ROOT/evals/fixtures/ts-bloated-cart" && npm ci --silent) || { echo "npm ci failed for ts-bloated-cart" >&2; exit 1; }
fi

python3 "$ROOT/evals/make_cases.py" >/dev/null   # cases always match evals/evals.json and triggers.py
{
  echo "suites=${SUITES[*]}"; echo "args=$*"; echo "started=$(date -u +%FT%TZ)"
  echo "git=$(git -C "$ROOT" rev-parse --short HEAD)$(git -C "$ROOT" diff --quiet || echo '+dirty')"
  echo "python=$(command -v "$PY") $("$PY" --version 2>&1)"; echo "node=$(node --version 2>/dev/null)"
} > "$DIR/run.env"

# Pin the agent model so results are comparable across runs and with the skill-creator benchmark.
MODEL="${EVAL_MODEL:-claude-opus-5-5}"; echo "model=$MODEL" >> "$DIR/run.env"
PUBLISH=(--no-publish); for a in "$@"; do [[ "$a" == --publish-report ]] && PUBLISH=(); done
worst=0
for s in "${SUITES[@]}"; do
  case "$s" in
    trigger) ARGS=(--tag trigger --ablation none -j 8) ;;
    # Task agents must run the suite and edit files. plugin eval gates Bash/Write/Edit behind an
    # operator grant, whatever the case's allowed_tools say; without it every agent is read-only.
    # --keep-temp keeps each run's workspace so grade.py can check it objectively afterwards.
    task)    ARGS=(--tag task -j 5 --allow-tools Bash Write Edit --keep-temp) ;;   # default ablation: with and without
  esac
  echo "$s running" >> "$DIR/status"
  echo "[$(date +%T)] $s -> $DIR/$s.log"
  # --scaffold runs our own case scripts (they copy a fixture into the workspace);
  # --trust-plugin skips the interactive trust prompt, which would otherwise wait unseen.
  CMD=(claude --debug-file "$DIR/$s.debug.log" plugin eval . "${ARGS[@]}" --model "$MODEL" --verbose
       --scaffold --trust-plugin --threshold 0
       --json "$DIR/$s.json" --report "$DIR/$s.html" --output-dir "$DIR/$s" ${PUBLISH[@]+"${PUBLISH[@]}"} "$@")
  # script(1) gives the eval a terminal, so you keep its live progress display, and records
  # that display to $s.log; piping through tee would silence it until the end.
  if [[ "$(uname)" == Darwin ]]; then
    script -q "$DIR/$s.log" "${CMD[@]}"
  else
    script -qefc "$(printf '%q ' "${CMD[@]}")" "$DIR/$s.log"
  fi
  code=$?
  if [[ "$s" == task && -f "$DIR/task.json" ]]; then
    echo "[$(date +%T)] objective grading of the kept workspaces -> $DIR/task-objective.md"
    python3 "$ROOT/evals/grade_plugin_eval.py" "$DIR/task.json" --python "$PY" > /dev/null || echo "objective grading failed" >&2
  fi
  echo "$s exit=$code" >> "$DIR/status"
  (( code > worst )) && worst=$code
done
echo "finished=$(date -u +%FT%TZ) exit=$worst" > "$DIR/DONE"
echo "[$(date +%T)] done (exit $worst). Logs: $DIR"
exit "$worst"
