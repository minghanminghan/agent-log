"""Tests for agentlog.config."""

import json
from pathlib import Path

import pytest

from agentlog.config import load_config, DEFAULT_CONFIG


def test_global_only_config(tmp_path, monkeypatch):
    """Global-only config returns global values."""
    global_dir = tmp_path / ".agentlog"
    global_dir.mkdir()
    global_config = global_dir / "config.json"
    global_config.write_text(json.dumps({"log_tool_results": True}))

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".agentlog").mkdir()

    cfg = load_config(repo_root)
    assert cfg["log_tool_results"] is True


def test_local_config_overrides_global(tmp_path, monkeypatch):
    """Local config overrides global values for matching keys."""
    global_dir = tmp_path / ".agentlog"
    global_dir.mkdir()
    global_config = global_dir / "config.json"
    global_config.write_text(json.dumps({"log_tool_results": True, "content_max_chars": 5000}))

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)
    local_config = repo_root / ".agentlog" / "config.json"
    local_config.write_text(json.dumps({"content_max_chars": 999}))

    cfg = load_config(repo_root)
    assert cfg["log_tool_results"] is True     # from global
    assert cfg["content_max_chars"] == 999      # local wins


def test_missing_global_config_no_error(tmp_path, monkeypatch):
    """Missing global config file does not raise; defaults are returned."""
    no_config_home = tmp_path / "no_home"
    no_config_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: no_config_home)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)

    cfg = load_config(repo_root)
    # Should return defaults
    for key, val in DEFAULT_CONFIG.items():
        assert cfg[key] == val


def test_missing_local_config_no_error(tmp_path, monkeypatch):
    """Missing local config file does not raise; global values are returned."""
    global_dir = tmp_path / ".agentlog"
    global_dir.mkdir()
    global_config = global_dir / "config.json"
    global_config.write_text(json.dumps({"content_max_chars": 1234}))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)
    # No local config.json

    cfg = load_config(repo_root)
    assert cfg["content_max_chars"] == 1234


def test_defaults_present_when_no_files(tmp_path, monkeypatch):
    """All default keys are present when no config files exist."""
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: empty_home)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)

    cfg = load_config(repo_root)
    assert set(cfg.keys()) >= set(DEFAULT_CONFIG.keys())


def test_supported_and_active_defaults_are_empty_lists(tmp_path, monkeypatch):
    """supported and active default to empty lists."""
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: empty_home)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)

    cfg = load_config(repo_root)
    assert cfg["supported"] == []
    assert cfg["active"] == []


def test_supported_and_active_merge_from_local_config(tmp_path, monkeypatch):
    """supported and active are loaded from local config."""
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: empty_home)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)
    local_config = repo_root / ".agentlog" / "config.json"
    local_config.write_text(json.dumps({
        "supported": ["claude", "opencode"],
        "active": ["claude"],
    }))

    cfg = load_config(repo_root)
    assert cfg["supported"] == ["claude", "opencode"]
    assert cfg["active"] == ["claude"]


def test_local_active_overrides_global(tmp_path, monkeypatch):
    """Local active list overrides global active list."""
    global_dir = tmp_path / ".agentlog"
    global_dir.mkdir()
    global_config = global_dir / "config.json"
    global_config.write_text(json.dumps({"active": ["claude"]}))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo_root = tmp_path / "repo"
    (repo_root / ".agentlog").mkdir(parents=True)
    local_config = repo_root / ".agentlog" / "config.json"
    local_config.write_text(json.dumps({"active": ["opencode"]}))

    cfg = load_config(repo_root)
    assert cfg["active"] == ["opencode"]
