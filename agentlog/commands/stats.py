"""agentlog stats command."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from agentlog import repo as repo_mod
from agentlog.utils.time import parse_filename_date


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


@click.command("stats")
def stats():
    """Show session statistics."""
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
        click.echo("No sessions found.")
        return

    files = sorted(sessions_dir.glob("*.jsonl"))
    if not files:
        click.echo("No sessions found.")
        return

    total = len(files)
    total_size = sum(p.stat().st_size for p in files)
    avg_size = total_size / total if total else 0

    _min_dt = datetime.min.replace(tzinfo=timezone.utc)
    dates = [parse_filename_date(p) for p in files]
    valid_dates = [d for d in dates if d != _min_dt]
    oldest = min(valid_dates).strftime("%Y-%m-%d") if valid_dates else "unknown"
    newest = max(valid_dates).strftime("%Y-%m-%d") if valid_dates else "unknown"

    click.echo(f"Total sessions: {total}")
    click.echo(f"Total size:     {_format_size(total_size)}")
    click.echo(f"Average size:   {_format_size(int(avg_size))}")
    click.echo(f"Oldest session: {oldest}")
    click.echo(f"Newest session: {newest}")

    click.echo("\nLast 7 days:")
    now = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = sum(1 for d in valid_dates if d.date() == day)
        bar = "#" * count
        click.echo(f"  {day}  {count:3d}  {bar}")
