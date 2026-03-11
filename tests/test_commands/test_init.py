"""Tests for agentlog.commands.init."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def test_init_creates_sessions_dir(tmp_path, monkeypatch):
    """init creates .agentlog/sessions/."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".agentlog" / "sessions").is_dir()


def test_init_creates_config_json(tmp_path, monkeypatch):
    """init creates .agentlog/config.json."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    config_path = tmp_path / ".agentlog" / "config.json"
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert "log_tool_calls" in data


def test_init_writes_hook_entries(tmp_path, monkeypatch):
    """init writes correct hook entries to .claude/settings.json."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.is_file()
    settings = json.loads(settings_path.read_text())
    hooks = settings["hooks"]
    assert "UserPromptSubmit" in hooks
    assert "PreToolUse" in hooks
    assert "PostToolUse" in hooks
    assert "Stop" in hooks

    # Check specific commands
    up_cmds = [h["command"] for entry in hooks["UserPromptSubmit"] for h in entry.get("hooks", [])]
    assert "agentlog hook user-prompt" in up_cmds


def test_init_creates_settings_from_scratch(tmp_path, monkeypatch):
    """init creates .claude/settings.json when it does not exist."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    assert (tmp_path / ".claude" / "settings.json").is_file()


def test_init_merges_existing_settings(tmp_path, monkeypatch):
    """init merges into existing .claude/settings.json without overwriting unrelated keys."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps({"myCustomKey": "myValue", "otherSetting": 42}))

    runner = CliRunner()
    runner.invoke(cli, ["init"])

    settings = json.loads(settings_path.read_text())
    assert settings["myCustomKey"] == "myValue"
    assert settings["otherSetting"] == 42
    assert "hooks" in settings


def test_init_appends_gitignore(tmp_path, monkeypatch):
    """init appends .agentlog/ to .gitignore when gitignore: true."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    gitignore = tmp_path / ".gitignore"
    assert gitignore.is_file()
    assert ".agentlog/" in gitignore.read_text()


def test_init_no_duplicate_gitignore_entry(tmp_path, monkeypatch):
    """init does not duplicate .agentlog/ entry if already in .gitignore."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".agentlog/\n")
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    content = gitignore.read_text()
    assert content.count(".agentlog/") == 1


def test_init_idempotent(tmp_path, monkeypatch):
    """init is idempotent — running twice does not duplicate hook entries."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    runner.invoke(cli, ["init"])

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]

    # Check no duplicate entries
    up_cmds = [h["command"] for entry in hooks["UserPromptSubmit"] for h in entry.get("hooks", [])]
    assert up_cmds.count("agentlog hook user-prompt") == 1


# --- Agent detection tests ---

def test_init_detects_claude_when_claude_dir_exists(tmp_path, monkeypatch):
    """Auto-detects claude when .claude/ dir exists."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert "claude" in cfg["supported"]
    assert "claude" in cfg["active"]


def test_init_detects_opencode_when_opencode_dir_exists(tmp_path, monkeypatch):
    """Auto-detects opencode when .opencode/ dir exists."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".opencode").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert "opencode" in cfg["supported"]
    assert "opencode" in cfg["active"]


def test_init_detects_both_agents(tmp_path, monkeypatch):
    """Detects both agents when both dirs exist."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".opencode").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert "claude" in cfg["supported"]
    assert "opencode" in cfg["supported"]


def test_init_fails_when_no_agent_detected(tmp_path, monkeypatch):
    """Fails with non-zero exit and error message when neither agent is detected."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    # Patch shutil.which so opencode is not found on PATH either
    import shutil
    monkeypatch.setattr(shutil, "which", lambda x: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert "no supported coding agent detected" in result.output.lower() or \
           "no supported coding agent detected" in (result.stderr or "").lower()


def test_init_agent_flag_forces_claude(tmp_path, monkeypatch):
    """--agent claude forces claude even without .claude/ dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--agent", "claude"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert cfg["supported"] == ["claude"]
    assert cfg["active"] == ["claude"]


def test_init_agent_flag_forces_opencode(tmp_path, monkeypatch):
    """--agent opencode forces opencode even without .opencode/ dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--agent", "opencode"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert cfg["supported"] == ["opencode"]
    assert cfg["active"] == ["opencode"]


def test_init_config_contains_supported_and_active(tmp_path, monkeypatch):
    """Config file contains correct supported and active after init."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    cfg = json.loads((tmp_path / ".agentlog" / "config.json").read_text())
    assert "supported" in cfg
    assert "active" in cfg
    assert isinstance(cfg["supported"], list)
    assert isinstance(cfg["active"], list)


def test_init_opencode_writes_plugin_file(tmp_path, monkeypatch):
    """--agent opencode writes .opencode/plugins/agentlog.ts."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--agent", "opencode"])
    assert result.exit_code == 0
    plugin_path = tmp_path / ".opencode" / "plugins" / "agentlog.ts"
    assert plugin_path.is_file()
    content = plugin_path.read_text()
    assert "definePlugin" in content
    assert "agentlog hook" in content


def test_init_opencode_plugin_idempotent(tmp_path, monkeypatch):
    """Running init twice for opencode does not corrupt the plugin file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    runner = CliRunner()
    runner.invoke(cli, ["init", "--agent", "opencode"])
    first_content = (tmp_path / ".opencode" / "plugins" / "agentlog.ts").read_text()
    runner.invoke(cli, ["init", "--agent", "opencode"])
    second_content = (tmp_path / ".opencode" / "plugins" / "agentlog.ts").read_text()
    assert first_content == second_content


def test_init_claude_regression(tmp_path, monkeypatch):
    """--agent claude still creates .claude/settings.json."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--agent", "claude"])
    assert result.exit_code == 0
    assert (tmp_path / ".claude" / "settings.json").is_file()
