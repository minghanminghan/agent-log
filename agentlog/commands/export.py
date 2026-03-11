"""agentlog export command."""

import sys
from pathlib import Path

import click

from agentlog import repo as repo_mod
from agentlog import config as config_mod
from agentlog.commands.show import render_session, SEPARATOR
from agentlog.utils.session_io import read_session, find_session_file


def _export_json(records: list) -> None:
    import json
    for rec in records:
        click.echo(json.dumps(rec, ensure_ascii=False))


def _export_markdown(records: list, cfg: dict) -> None:
    max_chars = cfg.get("content_max_chars", -1)
    session_id = ""
    session_date = ""
    agent = "unknown"

    for rec in records:
        if rec.get("type") == "session_start":
            session_id = rec.get("session", "")[:8]
            t = rec.get("t", "")
            session_date = t[:16].replace("T", " ") if t else ""
            agent = rec.get("agent", "unknown")

    click.echo(f"# Session {session_id}")
    click.echo(f"\n**Date:** {session_date}  **Agent:** {agent}\n")

    for rec in records:
        rtype = rec.get("type", "")
        t = rec.get("t", "")

        if rtype == "user_msg":
            content = rec.get("content", "")
            if max_chars > 0 and len(content) > max_chars:
                content = content[:max_chars] + "..."
            click.echo(f"\n## User ({t[:19]})\n")
            click.echo(content)

        elif rtype == "assistant_msg":
            content = rec.get("content", "")
            if max_chars > 0 and len(content) > max_chars:
                content = content[:max_chars] + "..."
            click.echo(f"\n## Assistant ({t[:19]})\n")
            for line in content.splitlines():
                click.echo(f"> {line}")

        elif rtype == "tool_call":
            tool = rec.get("tool", "")
            file_path = rec.get("file", "")
            op = rec.get("op", "")
            lines_delta = rec.get("lines_delta")
            click.echo(f"\n## Tool Call: {tool} ({t[:19]})\n")
            click.echo("```")
            click.echo(f"tool: {tool}")
            if file_path:
                click.echo(f"file: {file_path}")
            if op:
                click.echo(f"op: {op}")
            if lines_delta is not None:
                click.echo(f"lines_delta: +{lines_delta}")
            click.echo("```")

        elif rtype == "tool_result":
            output = rec.get("output", "")
            if max_chars > 0 and len(output) > max_chars:
                output = output[:max_chars] + "..."
            click.echo(f"\n## Tool Result ({t[:19]})\n")
            click.echo("```")
            click.echo(output)
            click.echo("```")


def _do_export(records: list, fmt: str, cfg: dict) -> None:
    if fmt == "json":
        _export_json(records)
    elif fmt == "markdown":
        _export_markdown(records, cfg)
    elif fmt == "text":
        render_session(records, cfg)


@click.command("export")
@click.argument("session_id", required=False, default=None)
@click.option(
    "--format", "fmt", default="json",
    type=click.Choice(["json", "markdown", "text"]),
    help="Output format.",
)
@click.option("--all", "export_all", is_flag=True, default=False, help="Export all sessions.")
def export(session_id, fmt, export_all):
    """Export session(s) to stdout."""
    root = repo_mod.find_root(Path.cwd())
    if root is None:
        click.echo(
            "Error: agentlog not initialized in this directory."
            "Run 'agentlog init'.",
            err=True,
        )
        sys.exit(1)

    cfg = config_mod.load_config(root)
    sessions_dir = root / ".agentlog" / "sessions"

    if export_all:
        for path in sorted(sessions_dir.glob("*.jsonl")):
            try:
                records = read_session(path)
                _do_export(records, fmt, cfg)
            except OSError as e:
                sys.stderr.write(f"agentlog: warning: could not read {path}: {e}\n")
        return

    if session_id is None:
        click.echo("Error: provide a session ID or use --all.", err=True)
        sys.exit(1)

    session_file = find_session_file(sessions_dir, session_id)
    if session_file is None:
        click.echo(f"Error: session '{session_id}' not found.", err=True)
        sys.exit(1)

    try:
        records = read_session(session_file)
    except OSError as e:
        click.echo(f"Error: could not read session file {session_file}: {e}", err=True)
        sys.exit(1)

    _do_export(records, fmt, cfg)
