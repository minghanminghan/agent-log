"""Tests for agentlog.commands.status."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def test_status_initialized_yes(tmp_path, monkeypatch):
    """Shows 'initialized: yes' when .agentlog/ exists."""
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert "initialized: yes" in result.output


def test_status_initialized_no(tmp_path, monkeypatch):
    """Shows 'initialized: no' when .agentlog/ is absent."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert "initialized: no" in result.output


def test_status_hooks_active(tmp_path, monkeypatch):
    """Shows hooks as active when entries present in .claude/settings.json."""
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps({
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "agentlog hook stop"}]}]
        }
    }))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert "✓" in result.output or "active" in result.output.lower()


def test_status_session_count(tmp_path, monkeypatch):
    """Shows correct session count."""
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "2025-03-10_143022_abc12345.jsonl").write_text('{"v":1}\n')
    (sessions_dir / "2025-03-10_143023_def67890.jsonl").write_text('{"v":1}\n')
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert "2" in result.output
