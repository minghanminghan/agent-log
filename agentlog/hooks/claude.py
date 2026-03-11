"""Claude Code transcript reader."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def extract_assistant_turns(
    transcript_path: str, since_t: Optional[datetime] = None
) -> List[str]:
    """Extract assistant message text from a Claude Code transcript file.

    Reads the JSONL transcript at `transcript_path`, finds assistant role
    messages added after `since_t` (or all if None), and returns their
    text content strings.

    If the file cannot be parsed, returns an empty list (silent degradation).
    """
    try:
        p = Path(transcript_path)
        if not p.is_file():
            return []

        results = []
        with open(p, encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                # Extract the message object — may be top-level or under "message" key
                message = entry.get("message", entry)

                role = message.get("role", "")
                if role != "assistant":
                    continue

                # Filter by since_t if provided
                if since_t is not None:
                    # Try to parse timestamp from the entry
                    ts_str = entry.get("timestamp") or entry.get("t") or message.get("timestamp")
                    if ts_str:
                        try:
                            # Handle ISO 8601 with or without Z suffix
                            ts_str_clean = ts_str.replace("Z", "+00:00")
                            ts = datetime.fromisoformat(ts_str_clean)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts <= since_t:
                                continue
                        except (ValueError, AttributeError):
                            pass

                # Extract text content
                content = message.get("content", "")
                if isinstance(content, str):
                    if content.strip():
                        results.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text.strip():
                                    results.append(text)
                        elif isinstance(block, str) and block.strip():
                            results.append(block)

        return results

    except Exception:
        return []
