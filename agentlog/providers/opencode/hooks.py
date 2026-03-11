"""OpenCode storage reader — extract assistant messages from OpenCode's message files."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def extract_assistant_turns(
    storage_dir: str, session_id: str, since_t: Optional[datetime] = None
) -> List[str]:
    """Extract assistant message text from OpenCode storage files.

    OpenCode stores messages as individual JSON files:
    ``<storage_dir>/message/<session_id>/msg_<msgID>.json``

    Each file has ``role`` (``"assistant"``/``"user"``) and a ``parts`` array
    with blocks of ``type: "text"``, ``type: "tool-invocation"``, etc.
    Timestamps are in ``createdAt`` or ``time`` fields.

    Returns a list of assistant text strings, filtered to those after
    ``since_t`` (if provided). Silent on all errors (missing dir, bad JSON).
    """
    try:
        messages_dir = Path(storage_dir) / "message" / session_id
        if not messages_dir.is_dir():
            return []

        results = []
        for msg_file in sorted(messages_dir.glob("msg_*.json")):
            try:
                with open(msg_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            if data.get("role") != "assistant":
                continue

            # Filter by since_t
            if since_t is not None:
                ts_str = data.get("createdAt") or data.get("time") or data.get("t") or ""
                if ts_str:
                    try:
                        ts_clean = ts_str.replace("Z", "+00:00")
                        ts = datetime.fromisoformat(ts_clean)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts <= since_t:
                            continue
                    except (ValueError, AttributeError):
                        pass

            # Extract text content
            parts = data.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        if isinstance(text, str) and text.strip():
                            results.append(text)
            else:
                # Fallback: top-level content string
                content = data.get("content", "")
                if isinstance(content, str) and content.strip():
                    results.append(content)

        return results

    except Exception:
        return []
