#!/usr/bin/env bash
# Build a fresh eval workspace from a fixture: setup_ws.sh <fixture-name> <dest-dir>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/fixtures/$1"; DEST="$2"
mkdir -p "$(dirname "$DEST")"; [ ! -e "$DEST" ] || { echo "refusing: $DEST exists" >&2; exit 2; }
cp -cR "$FIX" "$DEST" 2>/dev/null || cp -R "$FIX" "$DEST"   # APFS clone when available (node_modules)
cd "$DEST"
if [ -x ./make_history.sh ]; then
  ./make_history.sh >/dev/null
else
  git init -q -b main && git add -A && git -c user.name=fixture -c user.email=fixture@example.com commit -qm "initial"
fi
echo "$DEST"
