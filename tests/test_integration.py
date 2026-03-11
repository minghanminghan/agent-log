"""Integration tests for the full agentlog pipeline."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_transcript(tmp_path: Path, content: str = "I refactored the auth module.") -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({
            "type": "say",
            "timestamp": "2025-03-10T14:30:52Z",
            "message": {"role": "assistant", "content": content},
        }) + "\n"
    )
    return transcript


def test_full_session_lifecycle(tmp_path, monkeypatch):
    """Full session lifecycle: init → hooks → log → show → search → stop."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()

    runner = CliRunner()

    # Init
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".agentlog" / "sessions").is_dir()

    transcript = _make_transcript(tmp_path)

    # Simulate UserPromptSubmit
    user_payload = {
        "session_id": "intg0001",
        "transcript_path": str(transcript),
        "prompt": "refactor the auth module to use JWT",
    }
    result = runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps(user_payload))
    assert result.exit_code == 0

    # Simulate PreToolUse
    pre_payload = {
        "session_id": "intg0001",
        "transcript_path": str(transcript),
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "src" / "auth.ts"), "content": "// jwt auth\nconst x = 1;"},
    }
    result = runner.invoke(cli, ["hook", "pre-tool"], input=json.dumps(pre_payload))
    assert result.exit_code == 0

    # Simulate PostToolUse (log_tool_results is false by default — no-op)
    post_payload = {
        "session_id": "intg0001",
        "transcript_path": str(transcript),
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "src" / "auth.ts")},
        "tool_response": {"output": "File written"},
    }
    result = runner.invoke(cli, ["hook", "post-tool"], input=json.dumps(post_payload))
    assert result.exit_code == 0

    # Simulate Stop
    stop_payload = {
        "session_id": "intg0001",
        "transcript_path": str(transcript),
        "stop_reason": "end_turn",
    }
    result = runner.invoke(cli, ["hook", "stop"], input=json.dumps(stop_payload))
    assert result.exit_code == 0

    # Check session file exists
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    session_files = list(sessions_dir.glob("*.jsonl"))
    assert len(session_files) == 1

    # Read and validate records
    records = []
    with open(session_files[0], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    types = [r["type"] for r in records]
    assert "session_start" in types
    assert "user_msg" in types
    assert "tool_call" in types
    assert "assistant_msg" in types
    assert "session_end" in types

    # agentlog log shows session
    result = runner.invoke(cli, ["log"])
    assert result.exit_code == 0
    assert "intg0001" in result.output

    # agentlog show renders records
    result = runner.invoke(cli, ["show", "intg0001"])
    assert result.exit_code == 0
    assert "USER" in result.output
    assert "ASSISTANT" in result.output
    assert "JWT" in result.output.upper() or "jwt" in result.output.lower()

    # agentlog search finds prompt text
    result = runner.invoke(cli, ["search", "auth module"])
    assert result.exit_code == 0
    assert "intg0001" in result.output

    # agentlog stop removes hooks
    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    # No agentlog hooks should remain
    hooks = settings.get("hooks", {})
    for event, entries in hooks.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                assert "agentlog hook" not in h.get("command", "")


def test_incomplete_session_log_and_show(tmp_path, monkeypatch):
    """Incomplete session (no Stop): log marks [incomplete], show renders with note."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    transcript = _make_transcript(tmp_path)
    user_payload = {
        "session_id": "incmp001",
        "transcript_path": str(transcript),
        "prompt": "help me",
    }
    runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps(user_payload))
    # No stop hook fired

    result = runner.invoke(cli, ["log"])
    assert "[incomplete]" in result.output

    result = runner.invoke(cli, ["show", "incmp001"])
    assert "[incomplete session]" in result.output


def test_two_concurrent_sessions(tmp_path, monkeypatch):
    """Two concurrent sessions produce separate files with no cross-contamination."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    transcript = _make_transcript(tmp_path)

    for sid in ["sess0001", "sess0002"]:
        payload = {
            "session_id": sid,
            "transcript_path": str(transcript),
            "prompt": f"prompt from {sid}",
        }
        runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps(payload))

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    session_files = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_files) == 2

    # Verify no cross-contamination
    for sf in session_files:
        records = []
        with open(sf, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        # Each file should have records for only one session
        session_starts = [r for r in records if r["type"] == "session_start"]
        assert len(session_starts) == 1


def test_prune_after_integration(tmp_path, monkeypatch):
    """prune correctly identifies old vs new files."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    # Create an old file manually
    old_file = sessions_dir / "2020-01-01_000000_claude_oldold12.jsonl"
    old_file.write_text(json.dumps({"v": 1, "type": "session_start"}) + "\n")

    # Create a recent file via hook
    transcript = _make_transcript(tmp_path)
    user_payload = {
        "session_id": "new00001",
        "transcript_path": str(transcript),
        "prompt": "recent prompt",
    }
    runner.invoke(cli, ["hook", "user-prompt"], input=json.dumps(user_payload))

    # Prune files older than 365 days
    result = runner.invoke(cli, ["prune", "--days", "365"])
    assert result.exit_code == 0
    assert not old_file.exists()

    remaining = list(sessions_dir.glob("*.jsonl"))
    assert any("new00001" in f.name for f in remaining)
