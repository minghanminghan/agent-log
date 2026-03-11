"""agentlog prune command — delete old session files."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from agentlog import repo as repo_mod


def _parse_filename_date(path: Path) -> datetime:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 2:
        try:
            dt = datetime.strptime(parts[0] + "_" + parts[1], "%Y-%m-%d_%H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


@click.command("prune")
@click.option("--days", default=None, type=int, help="Delete files older than N days.")
@click.option("--before", "before_date", default=None, help="Delete files before this date (YYYY-MM-DD).")
@click.option("--preview", is_flag=True, default=False, help="Preview without deleting.")
def prune(days, before_date, preview):
    """Delete old session files."""
    root = repo_mod.find_root(Path.cwd())
    if root is None:
        click.echo("Error: not inside an agentlog-initialized directory.", err=True)
        sys.exit(1)

    if days is None and before_date is None:
        click.echo("Specify --days N or --before YYYY-MM-DD.", err=True)
        sys.exit(1)

    sessions_dir = root / ".agentlog" / "sessions"
    if not sessions_dir.is_dir():
        click.echo("No sessions directory found.")
        return

    now = datetime.now(timezone.utc)

    cutoff = None
    if days is not None:
        cutoff = now - timedelta(days=days)
    if before_date is not None:
        try:
            cutoff = datetime.strptime(before_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            click.echo(f"Invalid date format: {before_date}. Use YYYY-MM-DD.", err=True)
            sys.exit(1)

    to_delete = []
    for path in sessions_dir.glob("*.jsonl"):
        file_date = _parse_filename_date(path)
        if file_date is None:
            continue
        if file_date < cutoff:
            to_delete.append(path)

    if not to_delete:
        click.echo("No files match the criteria.")
        return

    total_size = sum(p.stat().st_size for p in to_delete)
    label = "Would delete" if preview else "Deleting"
    click.echo(f"{label} {len(to_delete)} file(s)  ({_format_size(total_size)})")

    for path in sorted(to_delete):
        click.echo(f"  {path.name}")
        if not preview:
            path.unlink()

    if not preview:
        click.echo(f"Deleted {len(to_delete)} file(s).")
