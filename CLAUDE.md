# Claude Code hook integration

This document describes how `agentlog` integrates with Claude Code's hook system.

## How Claude Code hooks work

Claude Code supports user-defined hooks that fire as shell subprocesses on conversation events. Hooks are configured in `settings.json` -- either globally at `~/.claude/settings.json` or project-locally at `.claude/settings.json`. `agentlog` writes to the project-local file so hooks are scoped to the initialized directory.

The hook system supports five event types:

| Event | Fires |
|---|---|
| `UserPromptSubmit` | When the user submits a message, before Claude processes it |
| `PreToolUse` | Before every tool call |
| `PostToolUse` | After every tool call completes |
| `Notification` | On agent notifications (not used by agentlog) |
| `Stop` | When the agent finishes a turn |

Each hook entry specifies a `matcher` (tool name glob, or empty string for all tools) and a shell `command`. Claude Code runs the command as a subprocess and passes event data as JSON on stdin.

All hook payloads include a `transcript_path` field pointing to the current session's conversation file on disk. This is how `agentlog` reads assistant response content, which is not passed directly in any hook payload.

## Hook config written by `agentlog init`

`agentlog init` appends to `.claude/settings.json`. If the file does not exist it is created. If a hooks section already exists, agentlog merges into it.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "agentlog hook user-prompt"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentlog hook pre-tool"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentlog hook post-tool"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "agentlog hook stop"
          }
        ]
      }
    ]
  }
}
```

## Stdin payloads

Claude Code writes a JSON object to stdin for each hook invocation. All payloads include `session_id` and `transcript_path`.

### UserPromptSubmit

```json
{
  "session_id": "def456",
  "transcript_path": "/home/user/.claude/projects/abc/transcript.jsonl",
  "prompt": "refactor the auth module to use JWT"
}
```

`agentlog hook user-prompt` writes a `user_msg` record using the `prompt` field.

### PreToolUse

```json
{
  "session_id": "def456",
  "transcript_path": "/home/user/.claude/projects/abc/transcript.jsonl",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "src/auth.ts",
    "content": "..."
  }
}
```

### PostToolUse

```json
{
  "session_id": "def456",
  "transcript_path": "/home/user/.claude/projects/abc/transcript.jsonl",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "src/auth.ts",
    "content": "..."
  },
  "tool_response": {
    "output": "File written successfully"
  }
}
```

### Stop

```json
{
  "session_id": "def456",
  "transcript_path": "/home/user/.claude/projects/abc/transcript.jsonl",
  "stop_reason": "end_turn"
}
```

`agentlog hook stop` reads `transcript_path` to extract assistant messages written since the last `Stop`, writes `assistant_msg` records for each, then appends `session_end`.

## What `agentlog hook` does

The `agentlog hook <event>` subcommand is the single entry point called by all hooks. It:

1. Reads the JSON payload from stdin
2. Locates the `.agentlog/sessions/` directory by walking up from `$PWD`
3. Resolves the session file from `session_id` (creates it on first event if not present, writing `session_start`)
4. Appends the appropriate JSONL record:
   - `user-prompt` → writes a `user_msg` record from the `prompt` field; truncates content if `content_max_chars` is set
   - `pre-tool` → writes a `tool_call` record with a `call_id` (`<timestamp>_<tool_name>`); extracts and normalises the file path for Write/Edit/Read/MultiEdit tools; persists `call_id` to a temp file for post-tool correlation
   - `post-tool` → if `log_tool_results` is enabled, writes a `tool_result` record referencing the same `call_id` retrieved from the temp file; truncates output if `content_max_chars` is set
   - `stop` → reads `transcript_path`, extracts assistant turns written since the last stop, writes `assistant_msg` records (with optional truncation), then appends `session_end`; cleans up session ID and call_id temp files

If no `.agentlog/` directory is found in the directory tree, the hook exits silently with code 0. Hook commands never exit non-zero — all exceptions are caught and written to stderr so Claude Code can surface them as warnings without blocking the session.

## Hook removal (`agentlog stop`)

`agentlog stop` reads `.claude/settings.json`, removes the four hook entries written by agentlog (matched by command string), and rewrites the file. If the hooks arrays become empty after removal they are dropped. The `.agentlog/` directory is left intact.

## Session lifecycle

```
agentlog init
  └─ writes .claude/settings.json hook entries

user submits first prompt
  └─ UserPromptSubmit fires
       └─ agentlog hook user-prompt
            └─ session_start record written (session file created)
            └─ user_msg record written (content truncated if content_max_chars set)

... for each tool call ...
  PreToolUse fires
    └─ agentlog hook pre-tool
         └─ tool_call record written (call_id = <timestamp>_<tool_name>)
         └─ call_id persisted to <tempdir>/agentlog-calls-<ppid>.json

  PostToolUse fires
    └─ agentlog hook post-tool
         └─ if log_tool_results: true
              └─ call_id retrieved from temp file
              └─ tool_result record written with matching call_id

Stop fires
  └─ agentlog hook stop
       └─ reads transcript_path → extracts assistant turn(s) since last session_end
       └─ assistant_msg record(s) written (content truncated if content_max_chars set)
       └─ session_end record written
       └─ temp files cleaned up (<tempdir>/agentlog-<ppid>, agentlog-calls-<ppid>.json)

... subsequent turns repeat UserPromptSubmit → tools → Stop ...
```

## Notes

- The `session_id` in the stdin payload is the canonical session identifier. The session file is named `<timestamp>_<session_id[:8]>.jsonl` where the timestamp includes microseconds (`YYYY-MM-DD_HHMMSSffffff`) to prevent filename collisions between rapid concurrent hook calls.
- If the `agentlog` binary is not on PATH when a hook fires, the subprocess fails. Claude Code will display a hook warning. This is intentional -- silent failure would produce incomplete logs.
- `log_tool_results` controls whether `tool_response` content from PostToolUse is written. When false, the `tool_call` record is still written but no `tool_result` record is appended. When true, the `tool_result` includes a `call_id` that matches the preceding `tool_call`, enabling correlation.
- `content_max_chars` is applied at **write time** inside the hooks (not only at display time). Default is `-1` (no cap). Set to a positive integer to truncate prompts, assistant messages, and tool output before they are stored.
- Session ID fallback: if `session_id` is absent in the payload, agentlog reads/creates a temp file at `<tempdir>/agentlog-<ppid>`. The `call_id` correlation state is kept in a separate temp file `<tempdir>/agentlog-calls-<ppid>.json`. Both are cleaned up when the `stop` hook fires.
- File locking uses `fcntl.flock` on POSIX and `msvcrt.locking` on Windows to guard concurrent appends from multiple agent windows in the same repo.
- The `transcript_path` format is not officially documented by Anthropic. `agentlog hook stop` reads it to extract assistant message content. If the format changes between Claude Code versions, assistant message capture may break silently -- `tool_call` and `user_msg` records are unaffected.
- Sessions that have no tool calls (pure Q&A) still produce `user_msg` and `assistant_msg` records because `UserPromptSubmit` and `Stop` fire regardless of tool use.
- All errors in hook commands are written to stderr and never cause a non-zero exit. Configuration parse errors (malformed JSON, permission issues) also emit stderr warnings rather than silently falling back.
