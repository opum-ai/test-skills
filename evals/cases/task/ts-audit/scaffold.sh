#!/usr/bin/env bash
set -euo pipefail
FIX="$(cd "$(dirname "$0")/../../../fixtures/ts-bloated-cart" && pwd)"
cp -R "$FIX"/. .
[ -x ./make_history.sh ] && ./make_history.sh >/dev/null || (git init -q && git add -A && git -c user.email=e@e -c user.name=e commit -qm init)
