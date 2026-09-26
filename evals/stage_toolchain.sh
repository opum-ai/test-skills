#!/usr/bin/env bash
# Called by each task case's scaffold (outside the sandbox, cwd = the run's workspace, whose
# parent is the run's home). Clones the eval toolchain into <run home>/.tc, adds wrappers for
# python, git, npm and npx, and puts them on PATH via the run home's shell startup files, so
# the agent's tools work inside the sandbox without touching the workspace.
# shellcheck disable=SC2016  # $HOME must expand inside the run, not here
set -euo pipefail
SRC="${TS_EVAL_TOOLCHAIN:-/tmp/test-skills-toolchain}"
[[ -x "$SRC/python/bin/python3" ]] || { echo "no eval toolchain at $SRC: run evals/eval_toolchain.sh" >&2; exit 1; }
RUNHOME="$(cd .. && pwd)"; TC="$RUNHOME/.tc"
mkdir -p "$TC/bin"
cp -Rc "$SRC/python" "$TC/python" 2>/dev/null || cp -R "$SRC/python" "$TC/python"   # APFS clone when possible
# git: the /usr/bin shim needs xcrun's cache (unwritable in the sandbox); call a real binary.
GIT=""; for g in /opt/homebrew/bin/git /usr/local/bin/git /Library/Developer/CommandLineTools/usr/bin/git \
                 /Applications/Xcode.app/Contents/Developer/usr/bin/git; do [[ -x "$g" ]] && { GIT="$g"; break; }; done
w() { printf '#!/bin/sh\nexec %s "$@"\n' "$2" > "$TC/bin/$1"; chmod +x "$TC/bin/$1"; }
w python  '"$HOME/.tc/python/bin/python3"'; w python3 '"$HOME/.tc/python/bin/python3"'
[[ -n "$GIT" ]] && w git "$GIT"
# npm/npx: node's own binary runs, but npm's files usually live under your home (nvm), which is unreadable.
if NPM_BIN="$(command -v npm)"; then
  NPM_PKG="$(cd "$(dirname "$(readlink -f "$NPM_BIN")")/.." && pwd)"
  cp -Rc "$NPM_PKG" "$TC/npm" 2>/dev/null || cp -R "$NPM_PKG" "$TC/npm"
  w npm 'node "$HOME/.tc/npm/bin/npm-cli.js"'; w npx 'node "$HOME/.tc/npm/bin/npx-cli.js"'
fi
for rc in .zshenv .bashrc .bash_profile .profile; do
  printf 'export PATH="$HOME/.tc/bin:$PATH"\nexport NPM_CONFIG_UPDATE_NOTIFIER=false\n' >> "$RUNHOME/$rc"
done
