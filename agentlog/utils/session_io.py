"""Session file reading utilities shared across agentlog commands."""

import json
import sys
from pathlib import Path


def read_session(path: Path) -> list:
    """Read all valid JSONL records from a session file.

    Skips blank lines and malformed JSON with a stderr warning.
    Raises OSError if the file cannot be opened at all.
    """
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.stderr.write(
                    f"agentlog: warning: skipping malformed JSON at "
                    f"{path}:{lineno}: {e}\n"
                )
    return records


def find_session_file(sessions_dir: Path, prefix: str) -> "Path | None":
    """Find a session file whose stem contains the given prefix.

    Searches all *.jsonl files in sessions_dir sorted by name. Returns the
    first match, or None if no file matches.
    """
    for path in sorted(sessions_dir.glob("*.jsonl")):
        if prefix in path.stem:
            return path
    return None
