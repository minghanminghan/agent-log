"""Tests for agentlog.commands.hook."""

import json
import io
import sys
from pathlib import Path

import pytest

from click.testing import CliRunner
from agentlog.__main__ import cli


def _make_repo(tmp_path):
    """Create a minimal initialized repo."""
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    return tmp_path


def _run_hook(tmp_path, subcommand, payload, monkeypatch):
    """Run 'agentlog hook <subcommand>' with the given payload as stdin."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    stdin_data = json.dumps(payload)
    result = runner.invoke(cli, ["hook", subcommand], input=stdin_data)
    return result


def _read_session_records(sessions_dir: Path) -> list:
    records = []
    for f in sessions_dir.glob("*.jsonl"):
        with open(f, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def test_user_prompt_creates_session_start_and_user_msg(tmp_path, monkeypatch):
    """user-prompt with valid payload creates session_start + user_msg records in order."""
    _make_repo(tmp_path)
    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "prompt": "refactor auth",
    }
    _run_hook(tmp_path, "user-prompt", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    assert len(records) == 2
    assert records[0]["type"] == "session_start"
    assert records[1]["type"] == "user_msg"
    assert records[1]["content"] == "refactor auth"


def test_user_prompt_second_call_no_duplicate_session_start(tmp_path, monkeypatch):
    """Second user-prompt for same session appends only user_msg (no duplicate session_start)."""
    _make_repo(tmp_path)
    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "prompt": "first prompt",
    }
    _run_hook(tmp_path, "user-prompt", payload, monkeypatch)
    payload2 = dict(payload)
    payload2["prompt"] = "second prompt"
    _run_hook(tmp_path, "user-prompt", payload2, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    session_starts = [r for r in records if r["type"] == "session_start"]
    assert len(session_starts) == 1


def test_pre_tool_write_creates_tool_call_with_file(tmp_path, monkeypatch):
    """pre-tool Write tool writes tool_call with normalised file field."""
    _make_repo(tmp_path)
    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "src" / "auth.ts"),
            "content": "line1\nline2\nline3",
        },
    }
    _run_hook(tmp_path, "pre-tool", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    assert len(records) == 1
    rec = records[0]
    assert rec["type"] == "tool_call"
    assert rec["tool"] == "Write"
    assert "file" in rec
    assert rec["file"] == "src/auth.ts"
    assert rec["lines_delta"] == 3


def test_pre_tool_bash_no_file_field(tmp_path, monkeypatch):
    """pre-tool Bash tool writes tool_call without file field."""
    _make_repo(tmp_path)
    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }
    _run_hook(tmp_path, "pre-tool", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    assert len(records) == 1
    assert records[0]["type"] == "tool_call"
    assert "file" not in records[0]


def test_post_tool_log_results_false_writes_nothing(tmp_path, monkeypatch):
    """post-tool with log_tool_results: false writes nothing."""
    _make_repo(tmp_path)
    # Write a local config with log_tool_results: false
    config_path = tmp_path / ".agentlog" / "config.json"
    import json as _json
    config_path.write_text(_json.dumps({"log_tool_results": False}))

    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "tool_name": "Write",
        "tool_input": {"file_path": "test.ts"},
        "tool_response": {"output": "File written"},
    }
    _run_hook(tmp_path, "post-tool", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    assert len(records) == 0


def test_post_tool_log_results_true_writes_tool_result(tmp_path, monkeypatch):
    """post-tool with log_tool_results: true writes tool_result record."""
    _make_repo(tmp_path)
    config_path = tmp_path / ".agentlog" / "config.json"
    import json as _json
    config_path.write_text(_json.dumps({"log_tool_results": True}))

    payload = {
        "session_id": "abcd1234",
        "transcript_path": "/tmp/t.jsonl",
        "tool_name": "Write",
        "tool_input": {"file_path": "test.ts"},
        "tool_response": {"output": "File written successfully"},
    }
    _run_hook(tmp_path, "post-tool", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    assert len(records) == 1
    assert records[0]["type"] == "tool_result"
    assert records[0]["output"] == "File written successfully"


def test_stop_writes_assistant_msg_and_session_end(tmp_path, monkeypatch):
    """stop writes assistant_msg records and session_end."""
    _make_repo(tmp_path)

    # Create a fake transcript file
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_path.write_text(
        json.dumps({
            "type": "say",
            "timestamp": "2025-03-10T14:30:52Z",
            "message": {"role": "assistant", "content": "I refactored auth."},
        }) + "\n"
    )

    payload = {
        "session_id": "abcd1234",
        "transcript_path": str(transcript_path),
    }

    # First create a session_start so the session file exists
    user_payload = {
        "session_id": "abcd1234",
        "transcript_path": str(transcript_path),
        "prompt": "hello",
    }
    _run_hook(tmp_path, "user-prompt", user_payload, monkeypatch)
    _run_hook(tmp_path, "stop", payload, monkeypatch)

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = _read_session_records(sessions_dir)
    types = [r["type"] for r in records]
    assert "assistant_msg" in types
    assert types[-1] == "session_end"


def test_hook_outside_repo_exits_0_writes_nothing(tmp_path, monkeypatch):
    """Hook called outside initialised repo exits 0 and writes nothing."""
    # No .agentlog directory
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    payload = {"session_id": "abcd1234", "transcript_path": "/tmp/t.jsonl", "prompt": "hi"}
    result = runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps(payload))
    assert result.exit_code == 0
    # Nothing was written (no .agentlog)
    assert not (tmp_path / ".agentlog").exists()


def test_hook_never_exits_nonzero_on_bad_input(tmp_path, monkeypatch):
    """Hook commands must never exit non-zero even on malformed input."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["hook", "user-prompt"], input="not json at all")
    assert result.exit_code == 0
