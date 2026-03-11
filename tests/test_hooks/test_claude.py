"""Tests for agentlog.hooks.claude."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentlog.hooks.claude import extract_assistant_turns


def _write_transcript(path: Path, entries: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_extract_returns_assistant_text(tmp_path):
    """extract_assistant_turns returns text from assistant messages."""
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, [
        {"type": "say", "message": {"role": "user", "content": "hello"}},
        {"type": "say", "timestamp": "2025-03-10T14:30:52Z", "message": {"role": "assistant", "content": "I will help you."}},
    ])
    results = extract_assistant_turns(str(transcript), None)
    assert results == ["I will help you."]


def test_extract_multiple_assistant_messages(tmp_path):
    """extract_assistant_turns returns all assistant messages."""
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, [
        {"type": "say", "timestamp": "2025-03-10T14:30:52Z", "message": {"role": "assistant", "content": "First response."}},
        {"type": "say", "timestamp": "2025-03-10T14:31:00Z", "message": {"role": "assistant", "content": "Second response."}},
    ])
    results = extract_assistant_turns(str(transcript), None)
    assert len(results) == 2
    assert "First response." in results
    assert "Second response." in results


def test_extract_filters_by_since_t(tmp_path):
    """extract_assistant_turns with since_t filters out older messages."""
    transcript = tmp_path / "transcript.jsonl"
    since = datetime(2025, 3, 10, 14, 31, 0, tzinfo=timezone.utc)
    _write_transcript(transcript, [
        {"type": "say", "timestamp": "2025-03-10T14:30:52Z", "message": {"role": "assistant", "content": "Old message."}},
        {"type": "say", "timestamp": "2025-03-10T14:31:30Z", "message": {"role": "assistant", "content": "New message."}},
    ])
    results = extract_assistant_turns(str(transcript), since)
    assert results == ["New message."]


def test_extract_malformed_transcript_returns_empty(tmp_path):
    """extract_assistant_turns with malformed transcript returns empty list without raising."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("not json\nalso not json\n{broken\n")
    results = extract_assistant_turns(str(transcript), None)
    assert results == []


def test_extract_missing_file_returns_empty(tmp_path):
    """extract_assistant_turns with nonexistent file returns empty list."""
    results = extract_assistant_turns(str(tmp_path / "nonexistent.jsonl"), None)
    assert results == []


def test_extract_content_as_list_of_blocks(tmp_path):
    """extract_assistant_turns handles content as list of text blocks."""
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, [
        {
            "type": "say",
            "timestamp": "2025-03-10T14:30:52Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Block one."},
                    {"type": "tool_use", "id": "abc"},
                    {"type": "text", "text": "Block two."},
                ],
            },
        }
    ])
    results = extract_assistant_turns(str(transcript), None)
    assert "Block one." in results
    assert "Block two." in results


def test_extract_top_level_role_field(tmp_path):
    """extract_assistant_turns handles role at top-level (not wrapped in message)."""
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, [
        {"role": "assistant", "content": "Direct role message.", "timestamp": "2025-03-10T14:30:52Z"},
    ])
    results = extract_assistant_turns(str(transcript), None)
    assert "Direct role message." in results


def test_extract_since_t_exact_boundary(tmp_path):
    """Messages at exactly since_t are excluded (strictly after)."""
    transcript = tmp_path / "transcript.jsonl"
    since = datetime(2025, 3, 10, 14, 31, 0, tzinfo=timezone.utc)
    _write_transcript(transcript, [
        # Exactly at since_t — should be excluded
        {"type": "say", "timestamp": "2025-03-10T14:31:00Z", "message": {"role": "assistant", "content": "At boundary."}},
        # After since_t — should be included
        {"type": "say", "timestamp": "2025-03-10T14:31:01Z", "message": {"role": "assistant", "content": "After boundary."}},
    ])
    results = extract_assistant_turns(str(transcript), since)
    assert "At boundary." not in results
    assert "After boundary." in results
