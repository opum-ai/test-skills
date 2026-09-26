# Audit report contract

Results go to the user as a published Artifact page, not as terminal scroll. Load the
`artifact-design` skill before writing HTML, and `dataviz` for the charts. If no Artifact
tool exists, write `.tmx/reports/<date>-audit.html` and say so. When running as a subagent
that cannot publish, put the report content in the final message.

## Source of truth: `.tmx/findings.json`

Write it first, then build the page from it. `test-reduce` reads it.

```json
{
  "schema": "test-findings/1",
  "kind": "audit",
  "generated_at": "2026-09-26T12:00:00Z",
  "commit": "abc123",
  "summary": "One sentence verdict with numbers and the mutant scope",
  "scope": {"source": ["shop/"], "tests": ["tests/"], "operators": ["cmp", "..."],
            "per_line": 0, "history_mutants": 3, "excluded": ["what was not measured, and why"]},
  "inventory": {"tests": 172, "files": 9, "seconds": 4.1, "skipped": 2,
                "by_file": {"tests/test_cart.py": 31}},
  "adequacy": {"mutation": {"mutants": 210, "killed": 171, "score": 0.814},
               "by_tier": {"critical": {"score": 0.9}, "standard": {"score": 0.7}},
               "survivors_triaged": [{"mutant": "m0042", "where": "shop/tax.py:31",
                                      "verdict": "real-gap|equivalent", "missing_assertion": "..."}]},
  "redundancy": {"certified_minimum": 24, "optimal": true, "lower_bound": 24,
                 "reasons": {"zero-signal": 30, "duplicate": 40, "subsumed": 60, "jointly-covered": 18},
                 "curve": [[10, 0.8], [15, 0.9], [19, 0.95]], "plan": ".tmx/plan.json",
                 "certificate_verified": true},
  "clones": [{"size": 12, "tests": ["..."], "suggestion": "one parametrized table over the tier boundaries"}],
  "smells": {"by_kind": {"mock-heavy": 14}, "items_file": ".tmx/smells.json"},
  "ci": [{"id": "CI1", "severity": "high", "finding": "retry loop hides flakes", "article": "XI",
          "evidence": ".github/workflows/ci.yml:22", "recommendation": "..."}],
  "compliance": [{"article": "V", "status": "fail|pass|not-measured", "evidence": "..."}],
  "recommendations": [{"order": 1, "action": "...", "skill": "test-reduce", "impact": "-140 tests, -3.1s"}],
  "evidence": {"junit": ".tmx/junit.xml", "matrix": ".tmx/matrix.json", "plan": ".tmx/plan.json",
               "verify_log": ".tmx/verify.log", "smells": ".tmx/smells.json", "clones": ".tmx/clones.json"},
  "rerun": ["python3 .../tmx.py collect-pytest --src shop --tests tests -o .tmx/matrix.json", "..."]
}
```

## Write for the user, not for the tool

- Lead with the plain answer: "You need about 32 of your 175 tests; here is which, and why."
- Keep tool and framework vocabulary (tmx, obligations, articles, R-levels) out of the verdict
  strip and the recommendations. Put it in the evidence section.
- Put the per-test table (`analyze --csv`) where the user will look: link it from the
  report, next to the report file. It lists keep/remove, the reason, kills, unique kills, and
  the kept test that covers each removed one.
- State whether the **reduced suite itself** was re-run (`verify --rerun`). A certificate
  checked only against the matrix is weaker, and the report must say so.

## Required content, in this order

1. **Verdict strip.** One sentence and four numbers: tests now → certified minimum,
   suite seconds now → projected, mutation score (with its scope), and violations by article.
   For example: "172 tests → 24 certified (−86%), 4.1s → 0.6s; mutation 81% over 210 mutants
   (8 operators + 3 historical faults), unchanged by the cut; 5 of 13 articles failing."
2. **Reduction projection.** A before/after bar, plus the trade-off curve (tests kept against
   % of kills), with the certified point marked. Table of removal reasons, with counts and one
   example each.
3. **Consolidation opportunities.** The largest clone clusters, each with the rows that
   would become a parametrized table or the rule that would become a property.
4. **Weaknesses.** Surviving mutants in critical and standard code, triaged into real gaps
   (with the missing assertion) and equivalent mutants. A lean suite must also be strong
   enough.
5. **Smells.** Counts by kind and article, and the ten worst tests.
6. **CI findings.** Severity, the article each breaks, `file:line` evidence, and a
   recommendation.
7. **Constitution compliance.** One row per article: pass / fail / not measured, with evidence.
8. **What the numbers do not cover.** The mutant scope, the files excluded, the language
   gaps, and the reason `test-reduce` demotes to probation before deleting (ADR-0003).
9. **Re-run.** The exact commands, and where each evidence file is.

Save a copy to `.tmx/reports/` and reuse the same file path on republish, so the URL stays
stable.
