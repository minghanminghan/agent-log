"""Tests for agentlog.commands.stats."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_repo(tmp_path):
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    return tmp_path


def _make_session_file(sessions_dir: Path, dt: datetime, session_id: str) -> Path:
    ts = dt.strftime("%Y-%m-%d_%H%M%S")
    path = sessions_dir / f"{ts}_claude_{session_id[:8]}.jsonl"
    path.write_text(json.dumps({"v": 1, "type": "session_start"}) + "\n")
    return path


def test_stats_total_session_count(tmp_path, monkeypatch):
    """Correct total session count."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session_file(sessions_dir, now, "aaaa1111")
    _make_session_file(sessions_dir, now - timedelta(days=1), "bbbb2222")
    _make_session_file(sessions_dir, now - timedelta(days=2), "cccc3333")

    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0
    assert "3" in result.output


def test_stats_oldest_newest_dates(tmp_path, monkeypatch):
    """Correct oldest and newest dates parsed from filenames."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    old_dt = datetime(2025, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
    new_dt = datetime(2025, 3, 10, 14, 30, 0, tzinfo=timezone.utc)
    _make_session_file(sessions_dir, old_dt, "aaaa1111")
    _make_session_file(sessions_dir, new_dt, "bbbb2222")

    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert "2025-01-05" in result.output
    assert "2025-03-10" in result.output


def test_stats_last_7_days_breakdown(tmp_path, monkeypatch):
    """Per-day breakdown covers only the last 7 days."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session_file(sessions_dir, now, "today123")

    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert "Last 7 days" in result.output
    # Should show today's date
    today_str = now.strftime("%Y-%m-%d")
    assert today_str in result.output


def test_stats_no_sessions(tmp_path, monkeypatch):
    """No sessions prints message without error."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0
    assert "No sessions" in result.output
