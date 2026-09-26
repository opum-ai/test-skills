"""Engineering rigor profiles R1-R5 (docs/specs/engineering-rigor-profiles.md).

Each profile is a set of default gate rules. Explicit values in test-policy.toml override them.
Effective rigor for a change = max(project default, rigor of every touched tier, `Rigor:` trailer).
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

LEVELS = ["R1", "R2", "R3", "R4", "R5"]
NAMES = {"R1": "Minimal", "R2": "Lightweight", "R3": "Standard", "R4": "Strict", "R5": "High-Assurance"}

_BASE_SMELLS = ["no-assertion", "tautology", "swallowed-exception", "sleep", "skipped"]
_STRICT_SMELLS = _BASE_SMELLS + ["implementation-coupled", "snapshot-literal", "conditional-logic"]

PROFILES = {
    "R2": {"mode": "block", "forbid_smells": ["no-assertion", "tautology"], "max_mocks_per_test": None,
           "min_mutation_score": None, "require_unique_kill": False, "quarantine_days": 14,
           "quarantine_blocks": False, "probation_days": 3, "probation_runs": 3, "preserve_lines": False,
           "triage_survivors": False, "history_must_be_killed": False, "budget_exception": "trailer",
           "approval_required": False},
    "R3": {"mode": "block", "forbid_smells": _BASE_SMELLS, "max_mocks_per_test": 3, "min_mutation_score": 0.60,
           "require_unique_kill": True, "quarantine_days": 14, "quarantine_blocks": False,
           "probation_days": 14, "probation_runs": 20, "preserve_lines": False, "triage_survivors": False,
           "history_must_be_killed": False, "budget_exception": "trailer", "approval_required": False},
    "R4": {"mode": "block", "forbid_smells": _STRICT_SMELLS, "max_mocks_per_test": 2, "min_mutation_score": 0.80,
           "require_unique_kill": True, "quarantine_days": 7, "quarantine_blocks": False,
           "probation_days": 30, "probation_runs": 30, "preserve_lines": True, "triage_survivors": True,
           "history_must_be_killed": False, "budget_exception": "approval", "approval_required": False},
    "R5": {"mode": "block", "forbid_smells": _STRICT_SMELLS, "max_mocks_per_test": 2, "min_mutation_score": 0.90,
           "require_unique_kill": True, "quarantine_days": 0, "quarantine_blocks": True,
           "probation_days": 30, "probation_runs": 30, "preserve_lines": True, "triage_survivors": True,
           "history_must_be_killed": True, "budget_exception": "approval", "approval_required": True},
}
# R1 is advisory: it reports what R3 would flag, blocks nothing, and keeps no tests (no probation).
PROFILES["R1"] = dict(PROFILES["R3"], mode="advisory", probation_days=0, probation_runs=0)


def norm(level: Optional[str]) -> Optional[str]:
    if level is None:
        return None
    m = re.match(r"^\s*R?([1-5])\s*$", str(level), re.I)
    if not m:
        raise SystemExit(f"unknown rigor level {level!r}; expected one of {', '.join(LEVELS)}")
    return "R" + m.group(1)


def highest(levels: Iterable[Optional[str]]) -> str:
    got = [norm(x) for x in levels if x]
    return max(got, key=LEVELS.index) if got else "R3"


def declared(text: str) -> Optional[str]:
    """Highest `Rigor: R<n>` trailer in PR body / commit messages (it can only raise the level)."""
    found = re.findall(r"^Rigor:\s*(R?[1-5])\b", text or "", re.M | re.I)
    return highest(found) if found else None


def rules(level: str, policy: dict) -> dict:
    """Profile defaults for `level`, overridden by explicit policy values."""
    r = dict(PROFILES[norm(level)])
    adm = policy.get("admission", {})
    for k in ("forbid_smells", "max_mocks_per_test", "require_unique_kill"):
        if k in adm:
            r[k] = adm[k]
    fl = policy.get("flaky", {})
    if "quarantine_days" in fl:
        r["quarantine_days"] = fl["quarantine_days"]
    pb = policy.get("probation", {})
    if "days" in pb:
        r["probation_days"] = pb["days"]
    if "min_nightly_runs" in pb:
        r["probation_runs"] = pb["min_nightly_runs"]
    # Explicit policy may make a level stricter, never looser: every floor only rises.
    base = PROFILES[norm(level)]
    r["forbid_smells"] = sorted(set(r["forbid_smells"]) | set(base["forbid_smells"]))
    if base["max_mocks_per_test"] is not None:
        r["max_mocks_per_test"] = base["max_mocks_per_test"] if r["max_mocks_per_test"] is None \
            else min(r["max_mocks_per_test"], base["max_mocks_per_test"])
    if base["quarantine_days"] is not None:
        r["quarantine_days"] = base["quarantine_days"] if r["quarantine_days"] is None \
            else min(r["quarantine_days"], base["quarantine_days"])
    r["probation_days"] = max(r["probation_days"], base["probation_days"])
    r["probation_runs"] = max(r["probation_runs"], base["probation_runs"])
    for k in ("approval_required", "triage_survivors", "history_must_be_killed", "quarantine_blocks",
              "require_unique_kill", "preserve_lines"):
        r[k] = bool(r[k]) or bool(base[k])
    if base["budget_exception"] == "approval":
        r["budget_exception"] = "approval"
    r["level"] = norm(level)
    r["name"] = NAMES[r["level"]]
    return r
