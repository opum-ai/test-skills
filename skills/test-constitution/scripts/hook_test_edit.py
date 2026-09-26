#!/usr/bin/env python3
"""Claude Code PostToolUse hook: when an agent writes a test file in a project that has adopted
a test constitution, run the smell check on the tests it touched and block with the findings.

Install (project .claude/settings.json):
  {"hooks": {"PostToolUse": [{"matcher": "Write|Edit|MultiEdit",
     "hooks": [{"type": "command", "command": "python3 <plugin>/skills/test-constitution/scripts/hook_test_edit.py"}]}]}}

Reads the hook payload on stdin. Silent (exit 0) unless the file is a test file, the project has
test-policy.toml, and a forbidden smell appears in the edited file. Then it exits 2 with the
violations on stderr, which Claude Code feeds back to the agent. Fails open on any error.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "test-audit", "scripts"))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = (payload.get("tool_input") or {}).get("file_path") or ""
        if not re.search(r"(test_[^/]*\.py|_test\.py|\.(test|spec)\.[jt]sx?)$", path):
            return 0
        root = payload.get("cwd") or os.getcwd()
        d = os.path.dirname(os.path.abspath(path))
        while d != os.path.dirname(d) and not os.path.exists(os.path.join(d, "test-policy.toml")):
            d = os.path.dirname(d)
        policy_path = os.path.join(d, "test-policy.toml")
        if not os.path.exists(policy_path) or not os.path.exists(path):
            return 0
        from tmx import gate, smells
        policy = gate.load_policy(policy_path)
        adm = policy.get("admission", {})
        forbid = set(adm.get("forbid_smells", []))
        max_mocks = adm.get("max_mocks_per_test")
        items = smells.py_smells(path, policy.get("source", [])) if path.endswith(".py") else smells.js_smells(path)
        bad = []
        for s in items:
            if s["smell"] in forbid:
                bad.append(s)
            elif s["smell"] == "mock-heavy" and max_mocks:
                n = int(re.match(r"(\d+)", s["detail"]).group(1))
                if n > max_mocks:
                    bad.append(s)
        if not bad:
            return 0
        rel = os.path.relpath(path, d)
        lines = [f"Test constitution ({os.path.relpath(policy_path, root)}) violations in {rel}:"]
        lines += [f"- {s['test'].split('::', 1)[-1]} (line {s['line']}): {s['smell']}: {s['detail']}" for s in bad[:15]]
        lines.append("Fix these before continuing (see TEST-CONSTITUTION.md). If a test cannot be made to "
                     "assert real behavior, delete it.")
        print("\n".join(lines), file=sys.stderr)
        return 2
    except Exception:
        return 0  # never block on hook bugs


if __name__ == "__main__":
    sys.exit(main())
