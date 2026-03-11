"""Hook subcommand group: agentlog hook {user-prompt,pre-tool,post-tool,stop}."""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from agentlog import repo as repo_mod
from agentlog import session as session_mod
from agentlog import config as config_mod
from agentlog.hooks import claude
from agentlog.hooks import opencode as opencode_hook
from agentlog.utils.time import now_utc_iso, now_timestamp


# ---------------------------------------------------------------------------
# Session ID helpers (fallback when payload carries no stable ID)
# ---------------------------------------------------------------------------

def _session_id_file(ppid: int) -> Path:
    return Path(tempfile.gettempdir()) / f"agentlog-{ppid}"


def _calls_file(ppid: int) -> Path:
    """Temp file that maps session_id → last pre-tool call_id for post-tool correlation."""
    return Path(tempfile.gettempdir()) / f"agentlog-calls-{ppid}.json"


def _get_session_id(payload: dict) -> str:
    """Return session_id from payload, falling back to a per-parent-process temp file."""
    sid = payload.get("session_id", "") or ""
    if sid:
        return sid

    ppid = os.getppid()
    tmp = _session_id_file(ppid)
    if tmp.is_file():
        try:
            return tmp.read_text(encoding="utf-8").strip()
        except OSError as e:
            sys.stderr.write(f"agentlog: warning: could not read session ID file {tmp}: {e}\n")

    import secrets
    new_id = secrets.token_hex(4)
    try:
        tmp.write_text(new_id, encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"agentlog: warning: could not write session ID file {tmp}: {e}\n")
    return new_id


def _cleanup_session_files() -> None:
    """Delete the per-parent-process temp files for session ID and call IDs."""
    ppid = os.getppid()
    for tmp in (_session_id_file(ppid), _calls_file(ppid)):
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# call_id persistence (pre-tool → post-tool correlation)
# ---------------------------------------------------------------------------

def _store_call_id(session_id: str, call_id: str) -> None:
    """Persist the most recent call_id for a session so post-tool can retrieve it."""
    cf = _calls_file(os.getppid())
    try:
        data: dict = {}
        if cf.is_file():
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[session_id] = call_id
        cf.write_text(json.dumps(data), encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"agentlog: warning: could not persist call_id to {cf}: {e}\n")


def _retrieve_call_id(session_id: str) -> Optional[str]:
    """Retrieve the call_id stored by the most recent pre-tool for this session."""
    cf = _calls_file(os.getppid())
    try:
        if cf.is_file():
            data = json.loads(cf.read_text(encoding="utf-8"))
            return data.get(session_id)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Session file introspection helpers
# ---------------------------------------------------------------------------

def _get_last_session_end_time(session_file: Path) -> Optional[object]:
    """Return the datetime of the last session_end record, or None."""
    from datetime import datetime, timezone

    if not session_file.is_file():
        return None
    last_end = None
    try:
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("type") == "session_end":
                        t_str = rec.get("t", "")
                        if t_str:
                            clean = t_str.replace("Z", "+00:00")
                            last_end = datetime.fromisoformat(clean)
                except Exception:
                    continue
    except OSError as e:
        sys.stderr.write(f"agentlog: warning: could not read session file {session_file}: {e}\n")
    return last_end


def _session_has_start(session_file: Path) -> bool:
    """Return True if the session file already contains a session_start record."""
    if not session_file.is_file():
        return False
    try:
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("type") == "session_start":
                        return True
                except Exception:
                    continue
    except OSError as e:
        sys.stderr.write(f"agentlog: warning: could not read session file {session_file}: {e}\n")
    return False


# ---------------------------------------------------------------------------
# File-field extraction per tool name
# ---------------------------------------------------------------------------

# Maps tool name → tool_input key that holds the file path
_TOOL_FILE_FIELDS = {
    "Write": "file_path",
    "Edit": "file_path",
    "Read": "file_path",
    "MultiEdit": "file_path",
}

# Tools that write/modify files and report a line count
_WRITE_TOOLS = {"Write"}


# ---------------------------------------------------------------------------
# Content truncation helper
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars. max_chars <= 0 means no limit."""
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


# ---------------------------------------------------------------------------
# Click command group
# ---------------------------------------------------------------------------

@click.group()
def hook():
    """Internal hook handlers called by Claude Code."""
    pass


@hook.command("user-prompt")
def user_prompt():
    """Handle UserPromptSubmit hook."""
    try:
        payload = json.loads(sys.stdin.read())
        root = repo_mod.find_root(Path.cwd())
        if root is None:
            return

        cfg = config_mod.load_config(root)
        sessions_dir = root / ".agentlog" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        session_id = _get_session_id(payload)
        active = cfg.get("active", [])
        agent_name = active[0] if active else "claude"
        session_file = session_mod.resolve_session_file(sessions_dir, session_id, agent_name)

        now = now_utc_iso()

        if not _session_has_start(session_file):
            # Determine agent from active config list; default to "claude" for
            # backwards compatibility when active is empty (legacy installs).
            session_mod.append_record(session_file, {
                "v": 1,
                "type": "session_start",
                "t": now,
                "agent": agent_name,
                "session": session_id,
            })

        if cfg.get("log_user_messages", True):
            prompt_text = _truncate(
                payload.get("prompt", ""),
                cfg.get("content_max_chars", -1),
            )
            session_mod.append_record(session_file, {
                "v": 1,
                "type": "user_msg",
                "t": now,
                "content": prompt_text,
            })
    except Exception as e:
        sys.stderr.write(f"agentlog hook user-prompt: unexpected error: {e}\n")


@hook.command("pre-tool")
def pre_tool():
    """Handle PreToolUse hook."""
    try:
        payload = json.loads(sys.stdin.read())
        root = repo_mod.find_root(Path.cwd())
        if root is None:
            return

        cfg = config_mod.load_config(root)
        if not cfg.get("log_tool_calls", True):
            return

        sessions_dir = root / ".agentlog" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        session_id = _get_session_id(payload)
        agent_name = (cfg.get("active") or ["claude"])[0]
        session_file = session_mod.resolve_session_file(sessions_dir, session_id, agent_name)

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {}) or {}

        now = now_utc_iso()
        call_id = f"{now_timestamp()}_{tool_name}"

        record: dict = {
            "v": 1,
            "type": "tool_call",
            "t": now,
            "tool": tool_name,
            "call_id": call_id,
        }

        # Extract normalised file path for file-operating tools
        if tool_name in _TOOL_FILE_FIELDS:
            field = _TOOL_FILE_FIELDS[tool_name]
            raw_path = tool_input.get(field, "")
            if raw_path:
                record["file"] = session_mod.normalise_file_path(str(raw_path), root)
                record["op"] = "modified"

        # lines_delta for Write (content is known); skip for Edit (delta unknown)
        if tool_name in _WRITE_TOOLS:
            content = tool_input.get("content", "")
            if content:
                record["lines_delta"] = len(str(content).splitlines())

        session_mod.append_record(session_file, record)

        # Persist call_id so post-tool can link the result back to this record
        _store_call_id(session_id, call_id)

    except Exception as e:
        sys.stderr.write(f"agentlog hook pre-tool: unexpected error: {e}\n")


@hook.command("post-tool")
def post_tool():
    """Handle PostToolUse hook."""
    try:
        payload = json.loads(sys.stdin.read())
        root = repo_mod.find_root(Path.cwd())
        if root is None:
            return

        cfg = config_mod.load_config(root)
        if not cfg.get("log_tool_results", False):
            return

        sessions_dir = root / ".agentlog" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        session_id = _get_session_id(payload)
        agent_name = (cfg.get("active") or ["claude"])[0]
        session_file = session_mod.resolve_session_file(sessions_dir, session_id, agent_name)

        tool_name = payload.get("tool_name", "")
        tool_response = payload.get("tool_response", {}) or {}

        # Retrieve the call_id written by the matching pre-tool invocation
        call_id = _retrieve_call_id(session_id)

        output = _truncate(
            tool_response.get("output", ""),
            cfg.get("content_max_chars", -1),
        )

        record: dict = {
            "v": 1,
            "type": "tool_result",
            "t": now_utc_iso(),
            "tool": tool_name,
            "output": output,
        }
        if call_id is not None:
            record["call_id"] = call_id

        session_mod.append_record(session_file, record)

    except Exception as e:
        sys.stderr.write(f"agentlog hook post-tool: unexpected error: {e}\n")


@hook.command("stop")
def stop():
    """Handle Stop hook."""
    try:
        payload = json.loads(sys.stdin.read())
        root = repo_mod.find_root(Path.cwd())
        if root is None:
            _cleanup_session_files()
            return

        cfg = config_mod.load_config(root)
        sessions_dir = root / ".agentlog" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        session_id = _get_session_id(payload)
        active = cfg.get("active", [])
        agent_name = active[0] if active else "claude"
        session_file = session_mod.resolve_session_file(sessions_dir, session_id, agent_name)

        transcript_path = payload.get("transcript_path", "")
        since_t = _get_last_session_end_time(session_file)

        now = now_utc_iso()
        max_chars = cfg.get("content_max_chars", -1)

        if cfg.get("log_assistant_messages", True) and transcript_path:
            try:
                active = cfg.get("active", [])
                if "opencode" in active:
                    turns = opencode_hook.extract_assistant_turns(
                        transcript_path, session_id, since_t
                    )
                else:
                    turns = claude.extract_assistant_turns(transcript_path, since_t)
            except Exception as e:
                sys.stderr.write(
                    f"agentlog hook stop: could not extract assistant turns "
                    f"from {transcript_path}: {e}\n"
                )
                turns = []

            for turn_text in turns:
                session_mod.append_record(session_file, {
                    "v": 1,
                    "type": "assistant_msg",
                    "t": now,
                    "content": _truncate(turn_text, max_chars),
                })

        session_mod.append_record(session_file, {
            "v": 1,
            "type": "session_end",
            "t": now,
        })

        _cleanup_session_files()

    except Exception as e:
        sys.stderr.write(f"agentlog hook stop: unexpected error: {e}\n")
