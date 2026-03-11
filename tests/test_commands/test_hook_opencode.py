"""Smoke test: full hook pipeline for OpenCode-shaped payloads."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


SESSION_ID = "opencode_sess_001"


def _make_agentlog_dir(tmp_path: Path) -> Path:
    """Set up .agentlog/sessions/ and config with opencode active."""
    agentlog_dir = tmp_path / ".agentlog"
    sessions_dir = agentlog_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    config_path = agentlog_dir / "config.json"
    config_path.write_text(json.dumps({
        "log_tool_calls": True,
        "log_tool_results": True,
        "log_assistant_messages": True,
        "log_user_messages": True,
        "content_max_chars": -1,
        "gitignore": True,
        "supported": ["opencode"],
        "active": ["opencode"],
    }), encoding="utf-8")
    return sessions_dir


def _make_storage_dir(tmp_path: Path) -> Path:
    """Create OpenCode storage dir with a mock assistant message."""
    storage_dir = tmp_path / "opencode_storage"
    msg_dir = storage_dir / "message" / SESSION_ID
    msg_dir.mkdir(parents=True)
    (msg_dir / "msg_001.json").write_text(json.dumps({
        "role": "assistant",
        "parts": [{"type": "text", "text": "I will help you refactor."}],
        "createdAt": "2025-03-10T14:30:52Z",
    }), encoding="utf-8")
    return storage_dir


def _read_session_records(sessions_dir: Path, session_id: str) -> list:
    """Read all JSONL records from the session file for the given session_id."""
    prefix = session_id[:8]
    for f in sessions_dir.glob("*.jsonl"):
        if prefix in f.stem:
            records = []
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return records
    return []


def test_opencode_hook_pipeline(tmp_path, monkeypatch):
    """Full hook pipeline with OpenCode-shaped payloads produces correct JSONL records."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    sessions_dir = _make_agentlog_dir(tmp_path)
    storage_dir = _make_storage_dir(tmp_path)
    transcript_path = str(storage_dir)

    runner = CliRunner()

    # 1. user-prompt hook
    result = runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps({
        "session_id": SESSION_ID,
        "transcript_path": transcript_path,
        "prompt": "refactor auth module",
    }))
    assert result.exit_code == 0

    # 2. pre-tool hook
    result = runner.invoke(cli, ["hook", "pre-tool"], input=json.dumps({
        "session_id": SESSION_ID,
        "transcript_path": transcript_path,
        "tool_name": "write_file",
        "tool_input": {"path": "src/foo.ts", "content": "..."},
    }))
    assert result.exit_code == 0

    # 3. post-tool hook
    result = runner.invoke(cli, ["hook", "post-tool"], input=json.dumps({
        "session_id": SESSION_ID,
        "transcript_path": transcript_path,
        "tool_name": "write_file",
        "tool_input": {"path": "src/foo.ts", "content": "..."},
        "tool_response": {"output": "File written successfully"},
    }))
    assert result.exit_code == 0

    # 4. stop hook
    result = runner.invoke(cli, ["hook", "stop"], input=json.dumps({
        "session_id": SESSION_ID,
        "transcript_path": transcript_path,
        "stop_reason": "idle",
    }))
    assert result.exit_code == 0

    # 5. Read session records
    records = _read_session_records(sessions_dir, SESSION_ID)
    assert len(records) > 0

    types = [r["type"] for r in records]

    # session_start with agent=opencode
    assert "session_start" in types
    start = next(r for r in records if r["type"] == "session_start")
    assert start["agent"] == "opencode"

    # user_msg with correct content
    assert "user_msg" in types
    user = next(r for r in records if r["type"] == "user_msg")
    assert user["content"] == "refactor auth module"

    # tool_call record
    assert "tool_call" in types
    tool_call = next(r for r in records if r["type"] == "tool_call")
    assert tool_call["tool"] == "write_file"

    # tool_result record
    assert "tool_result" in types
    tool_result = next(r for r in records if r["type"] == "tool_result")
    assert "written" in tool_result.get("output", "").lower() or \
           tool_result.get("output") == "File written successfully"

    # assistant_msg from storage dir
    assert "assistant_msg" in types
    assistant = next(r for r in records if r["type"] == "assistant_msg")
    assert "refactor" in assistant["content"].lower() or "help" in assistant["content"].lower()

    # session_end
    assert "session_end" in types
