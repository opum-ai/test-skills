#!/usr/bin/env bash
# Build a fresh eval workspace from a fixture: setup_ws.sh <fixture-name> <dest-dir>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/fixtures/$1"; DEST="$2"
rm -rf "$DEST"; mkdir -p "$(dirname "$DEST")"; cp -R "$FIX" "$DEST"
cd "$DEST"
if [ -x ./make_history.sh ]; then
  ./make_history.sh >/dev/null
else
  git init -q -b main && git add -A && git -c user.name=fixture -c user.email=fixture@example.com commit -qm "initial"
fi
echo "$DEST"
