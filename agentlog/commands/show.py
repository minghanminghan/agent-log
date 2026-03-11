"""agentlog show command — display a session in detail."""

import sys
from pathlib import Path

import click

from agentlog import repo as repo_mod
from agentlog import config as config_mod
from agentlog.utils.session_io import read_session, find_session_file

SEPARATOR = "─" * 72


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars. max_chars <= 0 means no limit."""
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def _parse_time(t_str: str) -> str:
    """Return HH:MM:SS from an ISO timestamp string."""
    try:
        return t_str[11:19]
    except Exception:
        return "??:??:??"


def render_session(records: list, cfg: dict, out=None) -> None:
    """Render session records to output (defaults to stdout)."""
    if out is None:
        out = click.get_text_stream("stdout")

    max_chars = cfg.get("content_max_chars", -1)

    session_id = ""
    session_date = ""
    agent = "unknown"
    complete = False

    for rec in records:
        if rec.get("type") == "session_start":
            session_id = rec.get("session", "")[:8]
            t = rec.get("t", "")
            try:
                session_date = t[:10] + " " + t[11:16]
            except Exception:
                session_date = t
            agent = rec.get("agent", "unknown")
        if rec.get("type") == "session_end":
            complete = True

    click.echo(f"\nSession {session_id} -- {session_date} -- agent: {agent}", file=out)
    click.echo(SEPARATOR, file=out)

    for rec in records:
        rtype = rec.get("type", "")
        t = rec.get("t", "")
        time_str = _parse_time(t)

        if rtype == "user_msg":
            content = _truncate(rec.get("content", ""), max_chars)
            click.echo(f"\n[{time_str}] USER", file=out)
            for line in content.splitlines():
                click.echo(f"  {line}", file=out)

        elif rtype == "assistant_msg":
            content = _truncate(rec.get("content", ""), max_chars)
            click.echo(f"\n[{time_str}] ASSISTANT", file=out)
            for line in content.splitlines():
                click.echo(f"  {line}", file=out)

        elif rtype == "tool_call":
            tool = rec.get("tool", "")
            file_path = rec.get("file", "")
            op = rec.get("op", "")
            lines_delta = rec.get("lines_delta")

            parts = [f"[{time_str}] TOOL", tool]
            if file_path:
                parts.append(file_path)
            if op:
                parts.append(op)
            if lines_delta is not None:
                parts.append(f"+{lines_delta} lines")
            click.echo("  ".join(parts), file=out)

        elif rtype == "tool_result":
            output = _truncate(rec.get("output", ""), max_chars)
            click.echo(f"[{time_str}] RESULT  {output[:80]}", file=out)

    click.echo("", file=out)
    click.echo(SEPARATOR, file=out)

    if not complete:
        click.echo("\n[incomplete session]", file=out)


@click.command("show")
@click.argument("session_id")
def show(session_id):
    """Show a session in detail."""
    root = repo_mod.find_root(Path.cwd())
    if root is None:
        click.echo(
            "Error: not inside an agentlog-initialized directory. "
            "Run 'agentlog init' to initialize.",
            err=True,
        )
        sys.exit(1)

    cfg = config_mod.load_config(root)
    sessions_dir = root / ".agentlog" / "sessions"

    session_file = find_session_file(sessions_dir, session_id)
    if session_file is None:
        click.echo(
            f"Error: session '{session_id}' not found in {sessions_dir}.",
            err=True,
        )
        sys.exit(1)

    try:
        records = read_session(session_file)
    except OSError as e:
        click.echo(f"Error: could not read session file {session_file}: {e}", err=True)
        sys.exit(1)

    render_session(records, cfg)
