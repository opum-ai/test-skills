#!/usr/bin/env bash
set -euo pipefail
FIX="$(cd "$(dirname "$0")/../../../../fixtures/py-bloated-shop" && pwd)"
cp -R "$FIX"/. .
