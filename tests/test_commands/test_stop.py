"""Tests for agentlog.commands.stop."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_settings(tmp_path, hooks=None, extra=None):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings = extra or {}
    if hooks:
        settings["hooks"] = hooks
    path = claude_dir / "settings.json"
    path.write_text(json.dumps(settings))
    return path


def test_stop_removes_agentlog_hooks(tmp_path, monkeypatch):
    """stop removes exactly the four agentlog hook entries."""
    monkeypatch.chdir(tmp_path)
    _make_settings(tmp_path, hooks={
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "agentlog hook user-prompt"}]}],
        "PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "agentlog hook pre-tool"}]}],
        "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "agentlog hook post-tool"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "agentlog hook stop"}]}],
    })
    runner = CliRunner()
    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" not in settings or not settings.get("hooks")


def test_stop_leaves_unrelated_hooks(tmp_path, monkeypatch):
    """stop leaves unrelated hooks intact."""
    monkeypatch.chdir(tmp_path)
    _make_settings(tmp_path, hooks={
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": "agentlog hook user-prompt"}]},
            {"hooks": [{"type": "command", "command": "other-tool hook1"}]},
        ],
        "Stop": [{"hooks": [{"type": "command", "command": "agentlog hook stop"}]}],
    })
    runner = CliRunner()
    runner.invoke(cli, ["stop"])
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings.get("hooks", {})
    # UserPromptSubmit should still have the unrelated hook
    assert "UserPromptSubmit" in hooks
    cmds = [h["command"] for entry in hooks["UserPromptSubmit"] for h in entry.get("hooks", [])]
    assert "other-tool hook1" in cmds
    assert "agentlog hook user-prompt" not in cmds


def test_stop_drops_empty_hook_arrays(tmp_path, monkeypatch):
    """stop drops empty hook arrays after removal."""
    monkeypatch.chdir(tmp_path)
    _make_settings(tmp_path, hooks={
        "Stop": [{"hooks": [{"type": "command", "command": "agentlog hook stop"}]}],
    })
    runner = CliRunner()
    runner.invoke(cli, ["stop"])
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "Stop" not in settings.get("hooks", {})


def test_stop_no_error_if_no_settings_file(tmp_path, monkeypatch):
    """stop does not raise if .claude/settings.json does not exist."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0


def test_stop_does_not_touch_agentlog_dir(tmp_path, monkeypatch):
    """stop does not touch .agentlog/ directory."""
    monkeypatch.chdir(tmp_path)
    agentlog_dir = tmp_path / ".agentlog" / "sessions"
    agentlog_dir.mkdir(parents=True)
    session_file = agentlog_dir / "2025-03-10_143022_abc12345.jsonl"
    session_file.write_text('{"v":1,"type":"session_start"}\n')

    _make_settings(tmp_path, hooks={
        "Stop": [{"hooks": [{"type": "command", "command": "agentlog hook stop"}]}],
    })

    runner = CliRunner()
    runner.invoke(cli, ["stop"])

    # .agentlog still exists and session file is intact
    assert session_file.is_file()
    assert session_file.read_text() == '{"v":1,"type":"session_start"}\n'
