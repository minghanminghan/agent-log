# agentlog

> session logging for Claude Code.

`agentlog` captures the context behind your code -- the prompts, tool calls, and file changes made by Claude Code -- and stores them alongside your repository as a permanent, portable record. It bridges the gap between AI observability platforms (external, ephemeral) and version control (blind to how code was produced).

---

## Core concept

Every agent session writes a structured log file to `.agentlog/sessions/` in your repo root. Logs are append-only JSONL (one JSON object per line), one file per session. Each file captures:

- **User messages** -- the prompts you gave the agent
- **Assistant responses** -- what the agent said and reasoned
- **Tool calls** -- what the agent did (file writes, shell commands, searches)
- **File changes** -- which files were created, modified, or deleted, with line deltas
- **Session metadata** -- timestamp

> **Security note.** Session logs can capture sensitive content: credentials in prompts, secrets in tool output, private code, and internal queries. `log_tool_results` is off by default for this reason. Review what you commit before sharing `.agentlog/` with others, and consider keeping it in `.gitignore` for private or regulated repos.

```
.agentlog/
  README.md                              ← explains the folder to any newcomer
  config.json                            ← local config
  sessions/
    2025-03-10_143022123456_def456ab.jsonl   ← one file per agent conversation
    2025-03-10_091455887032_abc123de.jsonl
```

Filenames are `<timestamp>_<session-id>.jsonl` where the timestamp includes microseconds (`YYYY-MM-DD_HHMMSSffffff`) to prevent collisions between rapid hook calls, and the session ID is the first 8 characters of the agent's native conversation ID. Each new conversation — including after `/clear` — creates a new file.

### Session file format

```jsonl
{"v":1,"type":"session_start","t":"2025-03-10T14:30:22Z","agent":"claude","session":"def456ab"}
{"v":1,"type":"user_msg","t":"2025-03-10T14:30:45Z","content":"refactor the auth module to use JWT"}
{"v":1,"type":"assistant_msg","t":"2025-03-10T14:30:52Z","content":"I'll refactor the auth module to use JWT. Let me start by reading the current implementation."}
{"v":1,"type":"tool_call","t":"2025-03-10T14:31:02Z","tool":"write_file","file":"src/auth.ts","op":"modified","lines_delta":42}
{"v":1,"type":"tool_call","t":"2025-03-10T14:31:10Z","tool":"write_file","file":"src/auth.test.ts","op":"created","lines_delta":80}
{"v":1,"type":"assistant_msg","t":"2025-03-10T14:34:58Z","content":"Done. I've replaced the session-based auth with JWT. The token is signed with RS256 and expires in 1 hour. Tests updated."}
{"v":1,"type":"session_end","t":"2025-03-10T14:35:00Z"}
```

---

## Key design decisions

- **Shard files by session.** Each session gets its own file named by timestamp and session ID. Each new conversation — including after `/clear` -- creates a new file automatically.

- **Agent hooks registered on `agentlog init`.** Running `agentlog init` in a folder writes Claude Code hook configuration scoped to that directory. Hooks are calls back into the `agentlog` CLI -- no separate packages to install, no global configuration changed.

---

## Features

### For solo developers
- `agentlog log --days 3` -- show all logs from last 3 days
- `agentlog log --file src/auth.ts` -- see every agent session that touched a file

---

## Installation & setup

### 1. Install the CLI

```bash
pipx install agentlog
```

Requires Python 3.9+. `pipx` installs the CLI into an isolated environment and puts `agentlog` on your PATH. If you don't have `pipx`: `pip install --user pipx`.

### 2. Configure global defaults (optional)

`agentlog` reads global defaults from `~/.agentlog/config.json`. Create it once and every new repo will inherit these settings:

```bash
agentlog config init   # writes ~/.agentlog/config.json with defaults
```

```jsonc
// ~/.agentlog/config.json
{
  "log_tool_calls": true,
  "log_tool_results": false,    // off by default -- output can be large and may contain sensitive data
  "log_assistant_messages": true,
  "log_user_messages": true,
  "content_max_chars": -1,      // -1 = no cap; set to a positive integer to truncate at write time
  "gitignore": true             // add .agentlog/ to .gitignore on init by default
}
```

### 3. Initialize a repo

```bash
cd your-repo
agentlog init
```

This registers Claude Code hooks scoped to this directory, creates `.agentlog/sessions/`, copies your global config into `.agentlog/config.json`, and adds a `README.md` inside `.agentlog/` explaining the folder to newcomers.

```
$ agentlog init
✓ Detected: claude
✓ Hooks registered (directory-scoped)
✓ Initialized .agentlog/
✓ Added .agentlog/ to .gitignore
```

Per-repo config in `.agentlog/config.json` takes precedence over the global config.

---

## Usage

```bash
# View recent sessions
agentlog log
agentlog log --today
agentlog log --days 3

# View sessions for a specific file
agentlog log --file src/auth.ts

# View a specific session in full -- prompts, responses, tool calls
agentlog show <session-id>

# Search across all session content
agentlog search "JWT refactor"
agentlog search "auth" --file src/auth.ts

# Check logging status for the current directory
agentlog status

# Show storage stats
agentlog stats

# Delete old session files
agentlog prune --days 90
agentlog prune --before 2025-01-01
agentlog prune --preview        # preview what would be deleted

# Export sessions
agentlog export <session-id>
agentlog export <session-id> --format markdown
agentlog export --all --format json > archive.jsonl

# Remove hooks for the current directory (does not delete .agentlog/)
agentlog stop
```

### Example output

```
$ agentlog log --days 3

2025-03-10 14:30  def456ab  claude  4 tools  src/auth.ts src/auth.test.ts
2025-03-10 09:14  abc123de  claude  2 tools  src/main.ts
2025-03-09 16:45  xyz789fa  claude  7 tools  src/api.ts src/types.ts src/routes.ts
```

```
$ agentlog show def456ab

Session def456ab -- 2025-03-10 14:30 -- agent: claude
────────────────────────────────────────────────────────────────────────

[14:30:45] USER
  refactor the auth module to use JWT

[14:30:52] ASSISTANT
  I'll refactor the auth module to use JWT. Let me start by reading the
  current implementation.

[14:31:02] TOOL  write_file  src/auth.ts  modified  +42 lines
[14:31:10] TOOL  write_file  src/auth.test.ts  created  +80 lines

[14:34:58] ASSISTANT
  Done. I've replaced the session-based auth with JWT. The token is
  signed with RS256 and expires in 1 hour. Tests updated.

────────────────────────────────────────────────────────────────────────
```

```
$ agentlog status

agentlog initialized: yes
hooks active:
  claude  ✓  (.claude/settings.json)
sessions: 14  (2.1 MB)
config: .agentlog/config.json
gitignore: yes
```

---

## Implementation

### Architecture

```
agentlog/
  agentlog/
    __main__.py          -- CLI entry point
    repo.py              -- walk up from cwd to find .agentlog/ root
    session.py           -- JSONL writing, file locking, path normalisation
    config.py            -- load and merge global + local config.json
    utils/
      time.py            -- shared timestamp helpers (now_utc_iso, now_timestamp, parse_*)
      session_io.py      -- shared read_session() and find_session_file()
    hooks/
      claude.py          -- extract assistant turns from Claude Code transcripts
    commands/
      hook.py            -- user-prompt, pre-tool, post-tool, stop
      init.py
      stop.py
      log.py
      show.py
      search.py
      status.py
      stats.py
      prune.py
      export.py
      config.py
```

The CLI is a **Python** package installed via `pipx`. Hook registration writes to `.claude/settings.json` pointing back to the `agentlog` CLI -- no separate packages required.

### Record capture

| Record | Source |
|---|---|
| `user_msg` | `UserPromptSubmit` hook — `prompt` field passed directly in payload |
| `tool_call` | `PreToolUse` hook — file path normalised to repo-root-relative at write time |
| `tool_result` | `PostToolUse` hook — only written when `log_tool_results: true`; linked to its `tool_call` via `call_id` |
| `assistant_msg` | `Stop` hook — read from `transcript_path` provided in the payload |

See [CLAUDE.md](CLAUDE.md) for the full hook integration spec.

### File locking

`append_record` holds an exclusive lock for each write to guard against concurrent hook calls from multiple agent windows in the same repo:

- **POSIX (macOS / Linux):** `fcntl.flock(LOCK_EX)`
- **Windows:** `msvcrt.locking(LK_LOCK)` — retries automatically for up to 10 seconds

### Content truncation

`content_max_chars` is applied at **write time** inside the hooks, not just at display time. This keeps session files small when a cap is configured. The default is `-1` (no cap). Set it to a positive integer in `config.json` to truncate prompts and assistant messages before they are stored.

### `agentlog prune`

Scans `.agentlog/sessions/` and deletes JSONL files whose timestamp (parsed from the filename) is older than the specified threshold. `--preview` prints what would be deleted without removing anything. No daemon or cron required -- prune is a manual, explicit operation.

### `agentlog export`

Reads one or more session JSONL files and writes them to stdout in the requested format:

- **json** (default) -- re-emits the raw JSONL, suitable for piping or archiving
- **markdown** -- renders each event as a readable document with headings, code blocks for tool calls, and quoted assistant messages; useful for pasting into docs or issue comments
- **text** -- plain text, same as `agentlog show` but written to stdout for redirection

`--all` exports every session in `.agentlog/sessions/` in chronological order.
