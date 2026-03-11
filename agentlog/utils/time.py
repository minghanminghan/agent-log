"""Timestamp utilities shared across agentlog modules."""

from datetime import datetime, timezone
from pathlib import Path


def now_utc_iso() -> str:
    """Return current UTC time as ISO 8601 string (e.g. 2025-03-10T14:30:22Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_timestamp() -> str:
    """Return current UTC time as a filename-safe timestamp with microseconds.

    Format: YYYY-MM-DD_HHMMSSffffff (e.g. 2025-03-10_143022123456).
    Microseconds prevent filename collisions between rapid hook calls.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S%f")


def parse_iso_timestamp(t_str: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp string into a timezone-aware datetime.

    Handles both 'Z' suffix and '+00:00' offset. Returns datetime.min (UTC)
    on any parse failure rather than raising.
    """
    try:
        clean = t_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def parse_filename_date(path: Path) -> datetime:
    """Parse the date/time embedded in a session filename.

    Handles both formats:
      - Old: YYYY-MM-DD_HHMMSS_<id>.jsonl
      - New: YYYY-MM-DD_HHMMSSffffff_<id>.jsonl  (with microseconds)

    Returns datetime.min (UTC) if the filename cannot be parsed.
    """
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 2:
        date_time_str = parts[0] + "_" + parts[1]
        for fmt in ("%Y-%m-%d_%H%M%S%f", "%Y-%m-%d_%H%M%S"):
            try:
                dt = datetime.strptime(date_time_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.min.replace(tzinfo=timezone.utc)
