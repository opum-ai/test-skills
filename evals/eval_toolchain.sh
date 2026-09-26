#!/usr/bin/env bash
# Build the toolchain that `claude plugin eval` task agents use inside the eval OS sandbox.
#
# The sandbox cannot be configured (plugin-evals docs): the run's home replaces yours and your
# real home is unreadable; executables outside the run are denied (/tmp, /Volumes); and the
# /usr/bin xcrun shims (git, python3) fail because their per-user cache dir is unwritable.
# So we build a relocatable CPython (uv's standalone build) with the pinned deps here, once,
# and each task case's scaffold (which runs outside the sandbox) clones it into the run's
# home with evals/stage_toolchain.sh, which puts it on PATH through the run home's .zshenv.
#   evals/eval_toolchain.sh      # prints the toolchain dir (TS_EVAL_TOOLCHAIN, default below)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TC="${TS_EVAL_TOOLCHAIN:-/tmp/test-skills-toolchain}"
REQ="$ROOT/evals/requirements.txt"
stamp="$(cat "$REQ" "$0" | shasum | cut -c1-12)"
if [[ -f "$TC/.stamp" && "$(cat "$TC/.stamp")" == "$stamp" ]]; then echo "$TC"; exit 0; fi
command -v uv >/dev/null || { echo "uv not found: brew install uv" >&2; exit 1; }
uv python install --quiet "${PYTHON_VERSION:-3.12}" >&2
# The managed standalone build's real prefix (not a venv, not a symlinked version alias).
BASE="$("$(uv python find --managed-python --no-project "${PYTHON_VERSION:-3.12}")" -c 'import os, sys; print(os.path.realpath(sys.base_prefix))')"
rm -rf "$TC" && mkdir -p "$TC"
cp -R "$BASE/" "$TC/python"     # standalone builds are relocatable: the prefix follows the binary
[[ ! -L "$TC/python/bin/python3" || "$(readlink "$TC/python/bin/python3")" != /* ]] || { echo "toolchain python links out of $TC" >&2; exit 1; }
uv pip install --quiet --link-mode copy --break-system-packages --python "$TC/python/bin/python3" -r "$REQ" >&2
"$TC/python/bin/python3" -c "import pytest, coverage, hypothesis" >&2
echo "$stamp" > "$TC/.stamp"
echo "$TC"
