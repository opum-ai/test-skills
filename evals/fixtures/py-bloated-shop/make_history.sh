#!/usr/bin/env bash
# Build a plausible git history for this project, ending at exactly the current tree.
# Run from the project root of a fresh copy (one without a .git directory).
set -euo pipefail

if [ ! -d shop ] || [ ! -d tests ]; then
  echo "run this from the project root" >&2
  exit 2
fi
if [ -e .git ]; then
  echo ".git already exists; run this in a fresh copy" >&2
  exit 2
fi

orig="$(mktemp -d)"
trap 'rm -rf "$orig"' EXIT
cp -R shop tests "$orig/"

g() { git -c user.name=fixture -c user.email=fixture@example.com "$@"; }

commit() {  # commit <iso-date> <message> <paths...>
  local when="$1" msg="$2"
  shift 2
  git add -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" g commit -q -m "$msg"
}

replace() {  # replace <file> <old> <new>: exact, must match exactly once
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:]
text = open(path).read()
if text.count(old) != 1:
    sys.exit(f"replace: expected exactly one match in {path} for {old!r}, found {text.count(old)}")
open(path, "w").write(text.replace(old, new))
PY
}

drop_tests() {  # drop_tests <file> <test names...>: remove top-level test functions
  python3 - "$@" <<'PY'
import ast, sys
path, names = sys.argv[1], set(sys.argv[2:])
lines = open(path).read().splitlines(keepends=True)
spans = []
for node in ast.parse("".join(lines)).body:
    if isinstance(node, ast.FunctionDef) and node.name in names:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        end = node.end_lineno
        while end < len(lines) and not lines[end].strip():
            end += 1
        spans.append((start, end))
        names.discard(node.name)
if names:
    sys.exit(f"drop_tests: not found in {path}: {sorted(names)}")
for start, end in sorted(spans, reverse=True):
    del lines[start:end]
open(path, "w").write("".join(lines).rstrip("\n") + "\n")
PY
}

restore() { for f in "$@"; do cp "$orig/$f" "$f"; done; }

git init -q
g checkout -q -b main 2>/dev/null || true

# --- the code as first written, with three bugs that were fixed later ----------------------
replace shop/discounts.py \
  '    """A coupon is still valid on its expiry date and expires the day after."""
    return coupon.expires_on is not None and today > coupon.expires_on' \
  '    """True once the coupon has reached its expiry date."""
    return coupon.expires_on is not None and today >= coupon.expires_on'
replace shop/money.py 'from decimal import ROUND_HALF_UP, Decimal' 'from decimal import ROUND_HALF_EVEN, Decimal'
replace shop/money.py 'rounding=ROUND_HALF_UP)' 'rounding=ROUND_HALF_EVEN)'
replace shop/inventory.py '        if qty <= 0 or qty > held:' '        if qty <= 0:'
drop_tests tests/test_discounts.py test_coupon_is_valid_through_its_expiry_date
drop_tests tests/test_tax.py test_tax_rounds_half_cents_up
drop_tests tests/test_inventory.py test_releasing_more_than_reserved_raises

commit "2024-02-05T10:12:00+00:00" "Initial shop package: money, pricing, tax" \
  .gitignore pyproject.toml README.md shop tests/conftest.py tests/test_money.py tests/test_pricing.py tests/test_tax.py
commit "2024-02-09T15:40:00+00:00" "Add cart and coupon tests" \
  tests/test_cart.py tests/test_discounts.py

restore shop/discounts.py tests/test_discounts.py
commit "2024-02-20T09:03:00+00:00" "fix: coupon expiry off-by-one (coupons are valid through their expiry date)" \
  shop/discounts.py tests/test_discounts.py

commit "2024-03-01T11:27:00+00:00" "test: cover volume pricing tiers" tests/test_pricing_extra.py

restore shop/money.py tests/test_tax.py
commit "2024-03-14T16:55:00+00:00" "fix: tax rounding used banker's rounding; round half-up to the cent" \
  shop/money.py tests/test_tax.py

commit "2024-04-02T13:10:00+00:00" "Add inventory reservation and checkout flow tests" \
  tests/test_inventory.py tests/test_integration.py

restore shop/inventory.py tests/test_inventory.py
commit "2024-04-18T08:45:00+00:00" "fix: releasing more than was reserved drove available stock negative" \
  shop/inventory.py tests/test_inventory.py

commit "2024-05-06T17:20:00+00:00" "test: cart cases from support tickets" tests/test_cart_regression.py

git add -A
GIT_AUTHOR_DATE="2024-05-20T12:00:00+00:00" GIT_COMMITTER_DATE="2024-05-20T12:00:00+00:00" \
  g commit -q -m "ci: run the test suite on every push and pull request"

if [ -n "$(git status --porcelain)" ]; then
  echo "history does not end at the current tree" >&2
  exit 1
fi
git log --oneline
