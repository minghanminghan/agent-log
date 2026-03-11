"""Tests for agentlog.commands.config."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli
from agentlog.config import DEFAULT_CONFIG


def test_config_init_creates_file(tmp_path, monkeypatch):
    """config init writes ~/.agentlog/config.json with all expected default keys."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "init"])
    assert result.exit_code == 0

    config_path = home / ".agentlog" / "config.json"
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    for key in DEFAULT_CONFIG:
        assert key in data
        assert data[key] == DEFAULT_CONFIG[key]


def test_config_init_does_not_overwrite(tmp_path, monkeypatch):
    """config init does not overwrite an existing file."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    config_dir = home / ".agentlog"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    existing_data = {"custom_key": "custom_value", "log_tool_results": True}
    config_path.write_text(json.dumps(existing_data))

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "init"])
    assert result.exit_code == 0
    # File should not be overwritten
    data = json.loads(config_path.read_text())
    assert data == existing_data


def test_config_init_prints_path(tmp_path, monkeypatch):
    """config init prints the path of the created file."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "init"])
    assert result.exit_code == 0
    assert "config.json" in result.output or ".agentlog" in result.output
