"""Shared fixtures for agentlog tests."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary agentlog-initialized repo."""
    agentlog_dir = tmp_path / ".agentlog"
    sessions_dir = agentlog_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def sample_session_file(tmp_repo):
    """Create a sample session JSONL file."""
    sessions_dir = tmp_repo / ".agentlog" / "sessions"
    session_file = sessions_dir / "2025-03-10_143022_claude_def456ab.jsonl"
    records = [
        {"v": 1, "type": "session_start", "t": "2025-03-10T14:30:22Z", "agent": "claude", "session": "def456ab"},
        {"v": 1, "type": "user_msg", "t": "2025-03-10T14:30:45Z", "content": "refactor the auth module"},
        {"v": 1, "type": "assistant_msg", "t": "2025-03-10T14:30:52Z", "content": "I will refactor the auth module."},
        {"v": 1, "type": "tool_call", "t": "2025-03-10T14:31:02Z", "tool": "Write", "file": "src/auth.ts", "op": "modified", "lines_delta": 42},
        {"v": 1, "type": "session_end", "t": "2025-03-10T14:35:00Z"},
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return session_file
