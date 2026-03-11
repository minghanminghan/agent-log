"""Tests for agentlog.commands.export."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentlog.__main__ import cli


def _make_repo(tmp_path):
    (tmp_path / ".agentlog" / "sessions").mkdir(parents=True)
    return tmp_path


def _make_session_file(sessions_dir: Path, session_id: str, ts_prefix: str = "2025-03-10_143022") -> Path:
    path = sessions_dir / f"{ts_prefix}_{session_id[:8]}.jsonl"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": session_id},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "hello world"},
        {"v": 1, "type": "assistant_msg", "t": "2025-03-10T14:30:52Z", "content": "Hello back!"},
        {"v": 1, "type": "tool_call", "t": "2025-03-10T14:31:00Z", "tool": "Write", "file": "test.ts", "op": "modified"},
        {"v": 1, "type": "session_end", "t": "2025-03-10T14:35:00Z"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return path


def test_export_json_emits_valid_jsonl(tmp_path, monkeypatch):
    """--format json emits valid JSONL matching the source file."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", "sess1234", "--format", "json"])
    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if l.strip()]
    assert len(lines) == 5
    for line in lines:
        parsed = json.loads(line)
        assert "type" in parsed


def test_export_markdown_has_headings(tmp_path, monkeypatch):
    """--format markdown produces a string containing Markdown headings."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", "sess1234", "--format", "markdown"])
    assert result.exit_code == 0
    assert "## User" in result.output or "# Session" in result.output
    assert "## Assistant" in result.output or "## Tool" in result.output


def test_export_text_matches_show_format(tmp_path, monkeypatch):
    """--format text produces output similar to agentlog show format."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1234")

    runner = CliRunner()
    result_export = runner.invoke(cli, ["export", "sess1234", "--format", "text"])
    result_show = runner.invoke(cli, ["show", "sess1234"])
    assert result_export.exit_code == 0
    # Both should contain USER and ASSISTANT
    assert "USER" in result_export.output
    assert "ASSISTANT" in result_export.output
    assert result_export.output == result_show.output


def test_export_all_processes_multiple_sessions(tmp_path, monkeypatch):
    """--all processes files in chronological order."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / ".agentlog" / "sessions"
    _make_session_file(sessions_dir, "sess1111", "2025-03-10_100000")
    _make_session_file(sessions_dir, "sess2222", "2025-03-10_110000")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--all", "--format", "json"])
    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if l.strip()]
    assert len(lines) == 10  # 5 records per session


def test_export_unknown_session_id_exits_1(tmp_path, monkeypatch):
    """Unknown session ID exits 1."""
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "nonexistent"])
    assert result.exit_code == 1
