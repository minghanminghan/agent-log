"""Tests for agentlog.commands.show."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_repo(tmp_path):
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    return tmp_path


def _make_session_file(sessions_dir: Path, session_id: str, records: list) -> Path:
    ts = "2025-03-10_143022"
    path = sessions_dir / f"{ts}_{session_id[:8]}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return path


def test_show_renders_all_record_types(tmp_path, monkeypatch):
    """show renders user, assistant, and tool records in order."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": "def456ab"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "refactor auth"},
        {"v": 1, "type": "assistant_msg", "t": "2025-03-10T14:30:52Z", "content": "I will refactor."},
        {"v": 1, "type": "tool_call", "t": "2025-03-10T14:31:02Z", "tool": "Write", "file": "src/auth.ts", "op": "modified", "lines_delta": 10},
        {"v": 1, "type": "session_end", "t": "2025-03-10T14:35:00Z"},
    ]
    _make_session_file(sessions_dir, "def456ab", records)

    runner = CliRunner()
    result = runner.invoke(cli, ["show", "def456ab"])
    assert result.exit_code == 0
    assert "USER" in result.output
    assert "refactor auth" in result.output
    assert "ASSISTANT" in result.output
    assert "I will refactor." in result.output
    assert "TOOL" in result.output
    assert "src/auth.ts" in result.output


def test_show_session_prefix_match(tmp_path, monkeypatch):
    """show accepts a session ID prefix."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": "def456ab"},
        {"v": 1, "type": "session_end", "t": "2025-03-10T14:35:00Z"},
    ]
    _make_session_file(sessions_dir, "def456ab", records)

    runner = CliRunner()
    result = runner.invoke(cli, ["show", "def4"])
    assert result.exit_code == 0
    assert "def456ab" in result.output


def test_show_unknown_session_id_exits_1(tmp_path, monkeypatch):
    """show unknown session ID exits 1 with clear error."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["show", "nonexistent"])
    assert result.exit_code == 1


def test_show_incomplete_session_prints_note(tmp_path, monkeypatch):
    """Incomplete session prints note at end."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": "def456ab"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "hello"},
    ]
    _make_session_file(sessions_dir, "def456ab", records)

    runner = CliRunner()
    result = runner.invoke(cli, ["show", "def456ab"])
    assert "[incomplete session]" in result.output


def test_show_truncates_long_content(tmp_path, monkeypatch):
    """Long content is truncated to content_max_chars."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Write a local config with small max_chars
    config_path = tmp_path / ".agentlog" / "config.json"
    config_path.write_text(json.dumps({"content_max_chars": 10}))

    sessions_dir = tmp_path / ".agentlog" / "sessions"
    long_content = "A" * 100
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": "def456ab"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": long_content},
        {"v": 1, "type": "session_end", "t": "2025-03-10T14:35:00Z"},
    ]
    _make_session_file(sessions_dir, "def456ab", records)

    runner = CliRunner()
    result = runner.invoke(cli, ["show", "def456ab"])
    assert "A" * 100 not in result.output
    assert "..." in result.output
