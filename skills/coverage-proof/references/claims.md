# Claim records: `testing/claims/<unit>.json`

```json
{
  "id": "C-redeem-1",
  "unit": "loyalty.redeem",
  "rung": "property-subsumption",
  "statement": "test_redeem_rules (1 property + 3 anchors) checks everything the 24 former example tests checked",
  "hypothesis": "mutant scope: tmx python-ast operators cmp,arith,bool,not,const,return,cond,stmt on loyalty/redeem.py; history depth 20",
  "oracle": "SPEC.md §3 rules restated as predicates; no call into redeem() on the expected side",
  "evidence": [
    {"cmd": "tmx.py subsumes .tmx/matrix.json --by '*test_redeem_rules*' --tests '*test_redeem_example_*'",
     "result": "SUBSUMED (41/41 kills)", "log": ".tmx/evidence/C-redeem-1-subsumes.log"}
  ],
  "non_vacuity": "property kills 41 mutants; with the min-500 predicate removed it misses 3 (log: .tmx/evidence/C-redeem-1-vacuity.log)",
  "subsumes": ["tests/test_redeem.py::test_redeem_example_1", "..."],
  "conformance_test": "tests/test_redeem.py::test_redeem_rules",
  "assumptions": ["points are integers (enforced by the type and constructor)"],
  "rigor": "R3",
  "date": "2026-09-26"
}
```

| Rung | `statement` shape | Required evidence |
|---|---|---|
| kill-set certificate | "N tests retain every kill of M" | `analyze` plan, `verify` VALID, `compare` 0 lost |
| partition completeness | "complete at t-way under uniformity" | `covering` with missing = [], plus the model file |
| property subsumption | "property P subsumes tests T" | `subsumes` SUBSUMED, plus non-vacuity |
| bounded-exhaustive | "all inputs of size ≤ k agree with the oracle" | the enumeration count, the run log, and the oracle-mutation check |
| differential | "impl == model on n generated inputs" | the generator, n, seeds, the model's own review or proof |
| proof / model check | "property holds (bounds / ∀)" | proof-skills findings.json, evidence logs, trust audit |
| statistical | "p_fail < 3/n at 95% under distribution D" | n, D, and the statement that D ≠ the operational profile unless shown |
