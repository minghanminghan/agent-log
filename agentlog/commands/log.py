"""agentlog log command — list sessions."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from agentlog import repo as repo_mod
from agentlog.session import normalise_file_path
from agentlog.utils.time import parse_filename_date, parse_iso_timestamp
from agentlog.utils.session_io import read_session


def _parse_session_file(path: Path):
    """Parse a session JSONL file and return a summary dict, or None on failure."""
    try:
        records = read_session(path)
    except OSError as e:
        sys.stderr.write(f"agentlog: warning: could not read {path}: {e}\n")
        return None

    if not records:
        return None

    summary = {
        "path": path,
        "session_id": None,
        "agent": "unknown",
        "timestamp": None,
        "tool_calls": [],
        "files": [],
        "complete": False,
    }

    for rec in records:
        rtype = rec.get("type", "")
        if rtype == "session_start":
            summary["session_id"] = rec.get("session", "")
            summary["agent"] = rec.get("agent", "unknown")
            summary["timestamp"] = rec.get("t", "")
        elif rtype == "tool_call":
            summary["tool_calls"].append(rec)
            f = rec.get("file", "")
            if f and f not in summary["files"]:
                summary["files"].append(f)
        elif rtype == "session_end":
            summary["complete"] = True

    if not summary["session_id"]:
        # Derive from filename: 2025-03-10_143022_def456ab → def456ab
        parts = path.stem.rsplit("_", 1)
        summary["session_id"] = parts[-1] if len(parts) > 1 else path.stem

    if not summary["timestamp"]:
        # Derive datetime from filename; format as ISO for downstream parsing
        dt = parse_filename_date(path)
        if dt != datetime.min.replace(tzinfo=timezone.utc):
            summary["timestamp"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return summary


@click.command("log")
@click.option("--days", default=None, type=int, help="Show sessions from last N days.")
@click.option("--today", is_flag=True, default=False, help="Show only today's sessions.")
@click.option("--file", "file_filter", default=None, help="Show sessions touching this file.")
@click.option("--agent", "agent_filter", default=None, help="Show only sessions from this agent.")
def log(days, today, file_filter, agent_filter):
    """List recent agent sessions."""
    root = repo_mod.find_root(Path.cwd())
    if root is None:
        click.echo(
            "Error: agentlog not initialized in this directory."
            "Run 'agentlog init'.",
            err=True,
        )
        sys.exit(1)

    sessions_dir = root / ".agentlog" / "sessions"
    if not sessions_dir.is_dir():
        return

    now = datetime.now(timezone.utc)
    cutoff = None
    if today:
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif days is not None:
        cutoff = now - timedelta(days=days)

    norm_filter = normalise_file_path(file_filter, root) if file_filter else None

    summaries = []
    for path in sessions_dir.glob("*.jsonl"):
        summary = _parse_session_file(path)
        if summary is None:
            continue

        ts = parse_iso_timestamp(summary["timestamp"]) if summary["timestamp"] else None

        if cutoff is not None and ts is not None and ts < cutoff:
            continue

        if norm_filter is not None and norm_filter not in summary["files"]:
            continue

        if agent_filter is not None and summary["agent"] != agent_filter:
            continue

        summaries.append((ts, summary))

    # Sort newest first
    summaries.sort(
        key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    for ts, summary in summaries:
        date_str = ts.strftime("%Y-%m-%d %H:%M") if ts else "????-??-?? ??:??"
        sid = (summary["session_id"] or "")[:8]
        agent = summary["agent"]
        n_tools = len(summary["tool_calls"])
        files_str = " ".join(summary["files"][:5])
        incomplete = "" if summary["complete"] else "  [incomplete]"
        click.echo(f"{date_str}  {sid}  {agent}  {n_tools} tools  {files_str}{incomplete}")
