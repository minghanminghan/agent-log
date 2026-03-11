"""Tests for agentlog.commands.log."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_repo(tmp_path):
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    return tmp_path


def _make_session(sessions_dir: Path, session_id: str, dt: datetime, files=None, complete=True):
    """Create a minimal session JSONL file."""
    ts = dt.strftime("%Y-%m-%d_%H%M%S")
    t = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = sessions_dir / f"{ts}_{session_id[:8]}.jsonl"
    records = [
        {"v": 1, "type": "session_start", "t": t, "agent": "claude", "session": session_id},
        {"v": 1, "type": "user_msg", "t": t, "content": "test"},
    ]
    for f in (files or []):
        records.append({"v": 1, "type": "tool_call", "t": t, "tool": "Write", "file": f, "op": "modified"})
    if complete:
        records.append({"v": 1, "type": "session_end", "t": t})
    with open(path, "w", encoding="utf-8") as fp:
        for rec in records:
            fp.write(json.dumps(rec) + "\n")
    return path


def test_log_lists_sessions_newest_first(tmp_path, monkeypatch):
    """log lists sessions sorted newest-first."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    _make_session(sessions_dir, "aaaa1111", now - timedelta(days=2))
    _make_session(sessions_dir, "bbbb2222", now)

    runner = CliRunner()
    result = runner.invoke(cli, ["log"])
    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if l.strip()]
    # bbbb2222 should appear before aaaa1111
    idx_b = next(i for i, l in enumerate(lines) if "bbbb2222" in l)
    idx_a = next(i for i, l in enumerate(lines) if "aaaa1111" in l)
    assert idx_b < idx_a


def test_log_days_filter(tmp_path, monkeypatch):
    """--days 3 excludes sessions older than 3 days."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session(sessions_dir, "new12345", now - timedelta(days=1))
    _make_session(sessions_dir, "old12345", now - timedelta(days=10))

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "--days", "3"])
    assert "new12345" in result.output
    assert "old12345" not in result.output


def test_log_today_filter(tmp_path, monkeypatch):
    """--today includes only today's sessions."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session(sessions_dir, "today123", now)
    _make_session(sessions_dir, "yester12", now - timedelta(days=1))

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "--today"])
    assert "today123" in result.output
    assert "yester12" not in result.output


def test_log_file_filter_exact_match(tmp_path, monkeypatch):
    """--file src/auth.ts returns only sessions with a matching tool_call file."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session(sessions_dir, "auth1234", now, files=["src/auth.ts"])
    _make_session(sessions_dir, "main1234", now, files=["src/main.ts"])

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "--file", "src/auth.ts"])
    assert "auth1234" in result.output
    assert "main1234" not in result.output


def test_log_file_filter_no_partial_match(tmp_path, monkeypatch):
    """--file does not match partial path."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session(sessions_dir, "auth1234", now, files=["src/auth.ts"])

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "--file", "src/auth"])
    assert "auth1234" not in result.output


def test_log_incomplete_session_shows_marker(tmp_path, monkeypatch):
    """Incomplete session (no session_end) displays [incomplete]."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session(sessions_dir, "incmp123", now, complete=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["log"])
    assert "[incomplete]" in result.output


def test_log_empty_sessions_dir_no_error(tmp_path, monkeypatch):
    """Empty sessions directory prints nothing without error."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["log"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_log_outside_repo_exits_1(tmp_path, monkeypatch):
    """Outside initialised repo exits 1 with helpful message."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli, ["log"])
    assert result.exit_code == 1
