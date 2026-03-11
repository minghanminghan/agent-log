"""Tests for agentlog.commands.search."""

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


def test_search_finds_in_user_msg(tmp_path, monkeypatch):
    """search returns sessions containing the query in user_msg."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234", [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "session": "sess1234"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "refactor JWT auth"},
    ])

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "JWT"])
    assert "sess1234" in result.output


def test_search_finds_in_assistant_msg(tmp_path, monkeypatch):
    """search returns sessions containing the query in assistant_msg."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234", [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "session": "sess1234"},
        {"v": 1, "type": "assistant_msg", "t": "2025-03-10T14:30:52Z", "content": "I will refactor JWT."},
    ])

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "JWT"])
    assert "sess1234" in result.output


def test_search_case_insensitive(tmp_path, monkeypatch):
    """search is case-insensitive."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234", [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "session": "sess1234"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "Refactor JWT Auth"},
    ])

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "jwt auth"])
    assert "sess1234" in result.output


def test_search_file_filter(tmp_path, monkeypatch):
    """--file filter combined with query narrows results correctly."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"

    _make_session_file(sessions_dir, "auth1234", [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "session": "auth1234"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "refactor JWT"},
        {"v": 1, "type": "tool_call", "t": "2025-03-10T14:31:02Z", "tool": "Write", "file": "src/auth.ts"},
    ])

    sessions_dir2 = sessions_dir
    ts2 = "2025-03-10_150000"
    _make_session_file(sessions_dir, "main1234", [
        {"v": 1, "type": "session_start", "t": "2025-03-10T15:00:00Z", "session": "main1234"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T15:00:01Z", "content": "refactor JWT"},
        {"v": 1, "type": "tool_call", "t": "2025-03-10T15:00:02Z", "tool": "Write", "file": "src/main.ts"},
    ])

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "JWT", "--file", "src/auth.ts"])
    assert "auth1234" in result.output
    assert "main1234" not in result.output


def test_search_no_matches_exits_0(tmp_path, monkeypatch):
    """No matches prints nothing and exits 0."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234", [
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "hello world"},
    ])

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "nonexistent_query_xyz"])
    assert result.exit_code == 0
    assert result.output.strip() == ""
