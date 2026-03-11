"""Repository root discovery."""

from pathlib import Path
from typing import Optional


def find_root(start: Path) -> Optional[Path]:
    """Walk up from `start` looking for a directory containing `.agentlog/`.

    Returns the directory that contains `.agentlog/`, or None if not found.
    """
    current = start.resolve()
    while True:
        if (current / ".agentlog").is_dir():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent
