# Minimal gate job

The full tiered pipeline is in the `test-ci` skill. This is the smallest useful gate.

```yaml
# .github/workflows/test-gate.yml
name: test-gate
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"
      - run: pytest -q -m "not probation and not quarantine" --junitxml=report.xml
      - env: { TMX_PR_BODY: "${{ github.event.pull_request.body }}" }
        run: python3 tools/tmx/tmx.py gate --policy test-policy.toml --junit report.xml --base origin/${{ github.base_ref }}
```

`tools/tmx/` is a copy of the plugin's `skills/test-audit/scripts/` directory (stdlib
only). Commit `.test-baseline.json`, and refresh it with `tmx.py baseline` when an accepted
change lands.
