#!/usr/bin/env python3
"""tmx - test matrix toolkit: measure a test suite, find redundancy, reduce it with a certificate.

  tmx.py collect-pytest --src pkg --tests tests -o .tmx/matrix.json [--jobs 4] [--no-mutate]
  tmx.py import-stryker reports/mutation/mutation.json -o .tmx/matrix.json
  tmx.py import-pit target/pit-reports/mutations.xml -o .tmx/matrix.json
  tmx.py score     .tmx/matrix.json
  tmx.py analyze   .tmx/matrix.json -o .tmx/plan.json [--lines] [--objective count|time] [--keep GLOB]
  tmx.py verify    .tmx/plan.json .tmx/matrix.json
  tmx.py subsumes  .tmx/matrix.json --by "*::test_prop_*" --tests "*::test_discount_*"
  tmx.py compare   .tmx/before.json .tmx/after.json
  tmx.py probation add|install|record|status|prune ...
  tmx.py smells    tests/ [-o .tmx/smells.json]
  tmx.py clones    tests/                       # near-duplicate tests -> parametrize/property candidates
  tmx.py covering  model.json [--strength 2] [--generate]
  tmx.py baseline  --matrix .tmx/matrix.json [--junit report.xml]
  tmx.py gate      --policy test-policy.toml [--matrix .tmx/matrix.json] [--junit report.xml] [--base origin/main]

Stdlib only; Python 3.9+. `collect-pytest` must run with (or be pointed at, via --python) an
interpreter that has pytest and coverage installed. Exit codes: 0 ok, 1 findings/gate failed,
2 usage, 3 certificate invalid.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tmx.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
