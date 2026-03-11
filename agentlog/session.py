"""JSONL session file writing with file locking."""

import json
import sys
from pathlib import Path

from agentlog.utils.time import now_timestamp


def resolve_session_file(sessions_dir: Path, session_id: str) -> Path:
    """Find an existing session file or return a path for a new one.

    Matches files named `*_<session_id[:8]>.jsonl`. If found, returns that
    path. Otherwise returns a new path `<timestamp>_<session_id[:8]>.jsonl`.
    Timestamp includes microseconds to avoid collisions between rapid calls.
    """
    short_id = session_id[:8]
    pattern = f"*_{short_id}.jsonl"
    matches = sorted(sessions_dir.glob(pattern))
    if matches:
        return matches[0]
    timestamp = now_timestamp()
    return sessions_dir / f"{timestamp}_{short_id}.jsonl"


def append_record(path: Path, record: dict) -> None:
    """Serialise `record` to JSON and append it to `path`.

    Acquires an exclusive file lock before writing to guard against concurrent
    hook calls from multiple agent windows in the same repo.

    - POSIX (macOS / Linux): uses `fcntl.flock` (exclusive lock on the fd).
    - Windows: uses `msvcrt.locking` (LK_LOCK — retries for up to 10 s).

    Creates the file and any missing parent directories if they do not exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"

    if sys.platform == "win32":
        import msvcrt

        lock_size = 2**30  # 1 GiB — comfortably larger than any session file
        with open(path, "a", encoding="utf-8") as f:
            # Lock from position 0; LK_LOCK retries automatically for 10 s.
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, lock_size)
            except OSError:
                # Could not acquire lock — proceed unlocked rather than drop data.
                f.seek(0, 2)
                f.write(line)
                f.flush()
                return
            try:
                f.seek(0, 2)  # seek to end for the actual append
                f.write(line)
                f.flush()
            finally:
                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, lock_size)
                except OSError:
                    pass
    else:
        import fcntl

        with open(path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def normalise_file_path(raw: str, repo_root: Path) -> str:
    """Convert an absolute or `./`-prefixed path to repo-root-relative with forward slashes.

    If `raw` is already relative and has no leading `./`, it is returned as-is
    (with backslashes replaced by forward slashes).
    """
    # Normalise backslashes first
    normalised = raw.replace("\\", "/")

    # Strip leading `./`
    if normalised.startswith("./"):
        normalised = normalised[2:]

    # If absolute, make relative to repo_root
    try:
        p = Path(raw)
        if p.is_absolute():
            try:
                normalised = str(p.relative_to(repo_root)).replace("\\", "/")
            except ValueError:
                # Not under repo_root — keep as-is but use forward slashes
                normalised = str(p).replace("\\", "/")
    except Exception:
        pass

    return normalised
