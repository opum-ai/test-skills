#!/usr/bin/env bash
# Create the project's Python environment (.venv, git-ignored) with uv, from evals/requirements.txt.
#   evals/setup_env.sh            # Python 3.12 (override: PYTHON_VERSION=3.13)
# uv downloads the interpreter if it is not installed. Re-running is cheap and idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v uv >/dev/null || { echo "uv not found: brew install uv (or see https://docs.astral.sh/uv/)" >&2; exit 1; }
cd "$ROOT"
[ -x .venv/bin/python ] || uv venv --quiet --python "${PYTHON_VERSION:-3.12}" .venv
uv pip install --quiet --python .venv/bin/python -r evals/requirements.txt
.venv/bin/python -c "import pytest, coverage, hypothesis, sys; print(f'.venv ready: Python {sys.version.split()[0]}, pytest {pytest.__version__}, coverage {coverage.__version__}, hypothesis {hypothesis.__version__}')"
