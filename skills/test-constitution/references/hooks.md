# Edit-time guard for agents (optional; ask before installing)

The gate catches violations at PR time. This project-level Claude Code hook catches them
the moment an agent writes a test file, while the agent can still fix them cheaply. It
reads `test-policy.toml` and fails open on any error.

`.claude/settings.json` (project scope; merge with existing hooks):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {"type": "command",
           "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/tmx-hooks/hook_test_edit.py\""}
        ]
      }
    ]
  }
}
```

Copy `scripts/hook_test_edit.py` together with `../test-audit/scripts/tmx/` to
`tools/tmx-hooks/`, preserving the relative import layout, or point `command` at the
installed plugin path. Vendoring is sturdier.

**Behavior:**
- It stays silent unless the written file is a test file *and* a `test-policy.toml` exists
  above it.
- Otherwise it runs the smell check on that file. Any forbidden smell, or too many mocks,
  exits 2 and sends the list to the agent.

Verify the hook by writing a test with no assertion. The agent should be told about it
immediately. A hook that has never fired is not known to work.
