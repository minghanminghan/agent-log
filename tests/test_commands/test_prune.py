"""Tests for agentlog.commands.prune."""

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
    path.write_text(json.dumps({"v": 1}) + "\n")
    return path


def test_prune_days_deletes_old_files(tmp_path, monkeypatch):
    """--days 90 deletes files older than 90 days, leaves newer files."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    old_file = _make_session_file(sessions_dir, now - timedelta(days=100), "old12345")
    new_file = _make_session_file(sessions_dir, now - timedelta(days=1), "new12345")

    runner = CliRunner()
    result = runner.invoke(cli, ["prune", "--days", "90"])
    assert result.exit_code == 0
    assert not old_file.exists()
    assert new_file.exists()


def test_prune_before_date(tmp_path, monkeypatch):
    """--before 2025-01-01 deletes files before that date."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    old_file = _make_session_file(sessions_dir, datetime(2024, 12, 15, tzinfo=timezone.utc), "old12345")
    new_file = _make_session_file(sessions_dir, datetime(2025, 1, 15, tzinfo=timezone.utc), "new12345")

    runner = CliRunner()
    result = runner.invoke(cli, ["prune", "--before", "2025-01-01"])
    assert result.exit_code == 0
    assert not old_file.exists()
    assert new_file.exists()


def test_prune_preview_does_not_delete(tmp_path, monkeypatch):
    """--preview prints files without deleting them."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    old_file = _make_session_file(sessions_dir, now - timedelta(days=100), "old12345")

    runner = CliRunner()
    result = runner.invoke(cli, ["prune", "--days", "90", "--preview"])
    assert result.exit_code == 0
    assert "Would delete" in result.output
    assert old_file.exists()  # Not deleted


def test_prune_prints_count_and_size(tmp_path, monkeypatch):
    """Prints correct count and size of affected files."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session_file(sessions_dir, now - timedelta(days=100), "old12345")
    _make_session_file(sessions_dir, now - timedelta(days=200), "old23456")

    runner = CliRunner()
    result = runner.invoke(cli, ["prune", "--days", "90", "--preview"])
    # Should mention 2 files
    assert "2" in result.output


def test_prune_no_matching_files(tmp_path, monkeypatch):
    """No matching files exits 0 with a message."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    now = datetime.now(timezone.utc)
    _make_session_file(sessions_dir, now, "new12345")

    runner = CliRunner()
    result = runner.invoke(cli, ["prune", "--days", "90"])
    assert result.exit_code == 0
    assert "No files" in result.output
