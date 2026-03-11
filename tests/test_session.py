"""Tests for agentlog.session."""

import json
import sys
import threading
from pathlib import Path

import pytest

from agentlog.session import append_record, resolve_session_file, normalise_file_path


def test_append_record_creates_file(tmp_path):
    """append_record creates the file if it does not exist."""
    f = tmp_path / "test.jsonl"
    assert not f.exists()
    append_record(f, {"v": 1, "type": "test", "t": "2025-01-01T00:00:00Z"})
    assert f.exists()


def test_append_record_valid_json_lines(tmp_path):
    """append_record appends valid JSON lines; each line is independently parseable."""
    f = tmp_path / "session.jsonl"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-01-01T00:00:00Z"},
        {"v": 1, "type": "user_msg", "t": "2025-01-01T00:00:01Z", "content": "hello"},
        {"v": 1, "type": "session_end", "t": "2025-01-01T00:00:02Z"},
    ]
    for rec in records:
        append_record(f, rec)

    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert "v" in parsed
        assert "type" in parsed


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
def test_append_record_concurrent_no_interleaving(tmp_path):
    """append_record under concurrent calls produces no interleaved lines."""
    f = tmp_path / "concurrent.jsonl"
    n_threads = 10
    n_records_each = 20

    def writer(thread_id):
        for i in range(n_records_each):
            append_record(f, {"v": 1, "type": "test", "thread": thread_id, "i": i, "t": "2025-01-01T00:00:00Z"})

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == n_threads * n_records_each
    for line in lines:
        parsed = json.loads(line)
        assert "thread" in parsed


def test_resolve_session_file_existing(tmp_path):
    """resolve_session_file returns the existing file for a known session ID."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    existing = sessions_dir / "2025-03-10_143022_claude_def456ab.jsonl"
    existing.touch()

    result = resolve_session_file(sessions_dir, "def456ab")
    assert result == existing


def test_resolve_session_file_existing_with_long_id(tmp_path):
    """resolve_session_file truncates to 8 chars when matching."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    existing = sessions_dir / "2025-03-10_143022_claude_def456ab.jsonl"
    existing.touch()

    result = resolve_session_file(sessions_dir, "def456ab_extra_stuff")
    assert result == existing


def test_resolve_session_file_new(tmp_path):
    """resolve_session_file returns a new path with correct timestamp format for unknown session."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    result = resolve_session_file(sessions_dir, "newid123", "claude")
    assert result.parent == sessions_dir
    # Filename: YYYY-MM-DD_HHMMSSffffff_claude_newid123.jsonl
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2}_\d{12}_claude_newid123\.jsonl", result.name)


def test_normalise_file_path_absolute(tmp_path):
    """normalise_file_path handles absolute path."""
    repo_root = tmp_path
    abs_path = str(tmp_path / "src" / "auth.ts")
    result = normalise_file_path(abs_path, repo_root)
    assert result == "src/auth.ts"


def test_normalise_file_path_dot_prefix(tmp_path):
    """normalise_file_path handles ./- prefixed paths."""
    result = normalise_file_path("./src/auth.ts", tmp_path)
    assert result == "src/auth.ts"


def test_normalise_file_path_already_relative(tmp_path):
    """normalise_file_path handles already-relative paths."""
    result = normalise_file_path("src/auth.ts", tmp_path)
    assert result == "src/auth.ts"


def test_normalise_file_path_backslash(tmp_path):
    """normalise_file_path handles Windows-style backslash input."""
    result = normalise_file_path("src\\auth\\module.ts", tmp_path)
    assert result == "src/auth/module.ts"


def test_normalise_file_path_absolute_outside_repo(tmp_path):
    """normalise_file_path handles absolute path outside repo root."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Path outside repo
    result = normalise_file_path("/tmp/outside/file.ts", repo_root)
    assert "/" in result
    assert "\\" not in result
