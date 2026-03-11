"""agentlog search command — full-text search across sessions."""

import sys
from pathlib import Path

import click

from agentlog import repo as repo_mod
from agentlog.session import normalise_file_path
from agentlog.utils.session_io import read_session

_SEARCHABLE_TYPES = {"user_msg", "assistant_msg", "tool_result"}


@click.command("search")
@click.argument("query")
@click.option("--file", "file_filter", default=None, help="Narrow to sessions touching this file.")
def search(query, file_filter):
    """Search session content for QUERY."""
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

    query_lower = query.lower()
    norm_filter = normalise_file_path(file_filter, root) if file_filter else None

    for path in sorted(sessions_dir.glob("*.jsonl")):
        try:
            records = read_session(path)
        except OSError as e:
            sys.stderr.write(f"agentlog: warning: could not read {path}: {e}\n")
            continue

        session_id = ""
        files_touched = []
        for rec in records:
            if rec.get("type") == "session_start":
                session_id = rec.get("session", "")[:8]
            if rec.get("type") == "tool_call":
                f = rec.get("file", "")
                if f:
                    files_touched.append(f)

        if not session_id:
            session_id = path.stem.rsplit("_", 1)[-1][:8]

        if norm_filter is not None and norm_filter not in files_touched:
            continue

        for rec in records:
            rtype = rec.get("type", "")
            if rtype not in _SEARCHABLE_TYPES:
                continue
            content = rec.get("content", "") or rec.get("output", "") or ""
            if query_lower in content.lower():
                t = rec.get("t", "")
                snippet = content[:80].replace("\n", " ")
                click.echo(f"{session_id}  {t}  {rtype}  {snippet}")
