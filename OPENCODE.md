# OpenCode integration

This document describes how `agentlog` integrates with OpenCode's plugin system.

## How OpenCode plugins work

OpenCode supports TypeScript/JavaScript plugins placed in `.opencode/plugins/`.
Plugins call `definePlugin` from the `opencode/plugin` SDK and subscribe to
native events via `app.on(...)`. They run in the same Node.js process as OpenCode,
so they have access to `child_process` for shelling out to external commands.

## Plugin file written by `agentlog init`

`agentlog init` (or `agentlog init --agent opencode`) writes:

```
.opencode/plugins/agentlog.ts
```

The plugin subscribes to three OpenCode events and shells out to the appropriate
`agentlog hook` subcommand, passing JSON on stdin — the same subcommands used by
the Claude Code integration.

To remove the plugin, run:

```
agentlog stop --agent opencode
```

## Event → hook mapping

| OpenCode event | agentlog hook subcommand | Notes |
|---|---|---|
| `tool.execute.before` | `agentlog hook pre-tool` | Also fires `user-prompt` on first event per session if `userMessage` is available |
| `tool.execute.after` | `agentlog hook post-tool` | |
| `session.idle` | `agentlog hook stop` | Fires when the agent finishes a turn |

## Stdin payload shapes

### `agentlog hook user-prompt`

```json
{
  "session_id": "sess_abc123",
  "transcript_path": "/home/user/.opencode/storage",
  "prompt": "refactor the auth module"
}
```

### `agentlog hook pre-tool`

```json
{
  "session_id": "sess_abc123",
  "transcript_path": "/home/user/.opencode/storage",
  "tool_name": "write_file",
  "tool_input": {
    "path": "src/auth.ts",
    "content": "..."
  }
}
```

### `agentlog hook post-tool`

```json
{
  "session_id": "sess_abc123",
  "transcript_path": "/home/user/.opencode/storage",
  "tool_name": "write_file",
  "tool_input": { "path": "src/auth.ts", "content": "..." },
  "tool_response": { "output": "File written successfully" }
}
```

### `agentlog hook stop`

```json
{
  "session_id": "sess_abc123",
  "transcript_path": "/home/user/.opencode/storage",
  "stop_reason": "idle"
}
```

## `transcript_path` for OpenCode

For OpenCode, `transcript_path` is the **storage directory** (e.g.
`~/.opencode/storage`), not a single file. The `agentlog hook stop` handler
reads assistant messages from:

```
<transcript_path>/message/<session_id>/msg_*.json
```

Each message file has `role`, `parts` (array of typed blocks), and a timestamp
in `createdAt` or `time`. The `agentlog/hooks/opencode.py` module handles this.

## Session lifecycle

```
agentlog init --agent opencode
  └─ writes .opencode/plugins/agentlog.ts

user submits first prompt
  └─ tool.execute.before fires (first event for session)
       └─ agentlog hook user-prompt (if userMessage available)
            └─ session_start record written
            └─ user_msg record written
       └─ agentlog hook pre-tool
            └─ tool_call record written

  tool.execute.after fires
    └─ agentlog hook post-tool
         └─ tool_result record written (if log_tool_results: true)

session.idle fires
  └─ agentlog hook stop
       └─ reads storage_dir/message/<session_id>/msg_*.json
       └─ assistant_msg record(s) written
       └─ session_end record written

... subsequent turns repeat tool.execute.before → after → session.idle ...
```

## `session_start` agent field

When the `user-prompt` hook fires via the OpenCode plugin, the `session_start`
record includes `"agent": "opencode"` so sessions can be distinguished.

## `active` and `supported` config fields

`agentlog init` writes `supported` and `active` lists to `.agentlog/config.json`:

```json
{
  "supported": ["claude", "opencode"],
  "active": ["claude", "opencode"]
}
```

- `supported` — agents detected at init time (presence of `.claude/`, `.opencode/`,
  or `opencode` binary on PATH).
- `active` — agents currently enabled. Defaults to all supported agents.

Both lists are empty by default so legacy installs are unaffected until
`agentlog init` is re-run.

## Notes

- The plugin uses `spawnSync` from Node.js `child_process` with
  `{ input: JSON.stringify(payload) }`. Errors are written to `console.error`
  and never thrown — the plugin never interrupts OpenCode.
- If `agentlog` is not on PATH when the plugin fires, `spawnSync` will fail.
  The error is logged to `console.error` as a warning.
- The OpenCode storage format is not officially documented. If it changes
  between OpenCode versions, assistant message capture may break silently.
  `tool_call` and `user_msg` records are unaffected.
- Sessions that have no tool calls (pure Q&A) will only have `user_msg` and
  `assistant_msg` records since `tool.execute.before/after` won't fire; the
  `user-prompt` hook must be triggered separately in that case.
