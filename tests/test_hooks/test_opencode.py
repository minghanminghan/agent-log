"""Tests for agentlog.hooks.opencode."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentlog.hooks.opencode import extract_assistant_turns


SESSION_ID = "sess_abc123"


def _write_msg(messages_dir: Path, filename: str, data: dict) -> None:
    messages_dir.mkdir(parents=True, exist_ok=True)
    (messages_dir / filename).write_text(json.dumps(data), encoding="utf-8")


def _msgs_dir(storage_dir: Path) -> Path:
    return storage_dir / "message" / SESSION_ID


def test_extract_returns_assistant_text(tmp_path):
    """Returns text from assistant messages."""
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "Hello from assistant."}],
        "createdAt": "2025-03-10T14:30:52Z",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert results == ["Hello from assistant."]


def test_extract_multiple_messages(tmp_path):
    """Returns text from multiple assistant messages."""
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "First."}],
        "createdAt": "2025-03-10T14:30:52Z",
    })
    _write_msg(msgs, "msg_002.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "Second."}],
        "createdAt": "2025-03-10T14:31:00Z",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert "First." in results
    assert "Second." in results
    assert len(results) == 2


def test_extract_skips_user_messages(tmp_path):
    """Skips messages with role != 'assistant'."""
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "user",
        "parts": [{"type": "text", "text": "User input."}],
    })
    _write_msg(msgs, "msg_002.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "Assistant reply."}],
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert results == ["Assistant reply."]


def test_extract_filters_by_since_t(tmp_path):
    """Filters messages by since_t."""
    since = datetime(2025, 3, 10, 14, 31, 0, tzinfo=timezone.utc)
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "Old."}],
        "createdAt": "2025-03-10T14:30:52Z",
    })
    _write_msg(msgs, "msg_002.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "New."}],
        "createdAt": "2025-03-10T14:31:30Z",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, since)
    assert results == ["New."]


def test_extract_since_t_exact_boundary(tmp_path):
    """Messages at exactly since_t are excluded (strictly after)."""
    since = datetime(2025, 3, 10, 14, 31, 0, tzinfo=timezone.utc)
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "At boundary."}],
        "createdAt": "2025-03-10T14:31:00Z",
    })
    _write_msg(msgs, "msg_002.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "After boundary."}],
        "createdAt": "2025-03-10T14:31:01Z",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, since)
    assert "At boundary." not in results
    assert "After boundary." in results


def test_extract_graceful_on_missing_dir(tmp_path):
    """Returns empty list when storage dir does not exist."""
    results = extract_assistant_turns(str(tmp_path / "nonexistent"), SESSION_ID, None)
    assert results == []


def test_extract_graceful_on_missing_session_dir(tmp_path):
    """Returns empty list when session subdirectory does not exist."""
    results = extract_assistant_turns(str(tmp_path), "unknown_session", None)
    assert results == []


def test_extract_graceful_on_malformed_json(tmp_path):
    """Skips malformed JSON files without raising."""
    msgs = _msgs_dir(tmp_path)
    msgs.mkdir(parents=True)
    (msgs / "msg_001.json").write_text("not json", encoding="utf-8")
    (msgs / "msg_002.json").write_text(json.dumps({
        "role": "assistant",
        "parts": [{"type": "text", "text": "Valid."}],
    }), encoding="utf-8")
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert results == ["Valid."]


def test_extract_mixed_part_types(tmp_path):
    """Only extracts text from parts of type 'text', ignores tool-invocation etc."""
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [
            {"type": "text", "text": "Before tool."},
            {"type": "tool-invocation", "toolName": "read_file", "toolCallId": "x"},
            {"type": "text", "text": "After tool."},
        ],
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert "Before tool." in results
    assert "After tool." in results
    assert len(results) == 2


def test_extract_fallback_to_content_field(tmp_path):
    """Falls back to top-level 'content' string if parts is absent."""
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "content": "Fallback content.",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, None)
    assert results == ["Fallback content."]


def test_extract_uses_time_field_for_timestamp(tmp_path):
    """Uses 'time' field if 'createdAt' is absent."""
    since = datetime(2025, 3, 10, 14, 31, 0, tzinfo=timezone.utc)
    msgs = _msgs_dir(tmp_path)
    _write_msg(msgs, "msg_001.json", {
        "role": "assistant",
        "parts": [{"type": "text", "text": "With time field."}],
        "time": "2025-03-10T14:32:00Z",
    })
    results = extract_assistant_turns(str(tmp_path), SESSION_ID, since)
    assert results == ["With time field."]
