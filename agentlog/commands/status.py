"""agentlog status command."""

import json
from pathlib import Path

import click

from agentlog import repo as repo_mod

_AGENTLOG_COMMANDS = {
    "agentlog hook user-prompt",
    "agentlog hook pre-tool",
    "agentlog hook post-tool",
    "agentlog hook stop",
}


def _hooks_active(cwd: Path) -> bool:
    settings_path = cwd / ".claude" / "settings.json"
    if not settings_path.is_file():
        return False
    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
        hooks = settings.get("hooks", {})
        for event, entries in hooks.items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    if h.get("command") in _AGENTLOG_COMMANDS:
                        return True
    except Exception:
        pass
    return False


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


@click.command("status")
def status():
    """Show agentlog status for the current directory."""
    cwd = Path.cwd()
    root = repo_mod.find_root(cwd)

    agentlog_dir = (root / ".agentlog") if root else (cwd / ".agentlog")
    initialized = root is not None and agentlog_dir.is_dir()

    click.echo(f"agentlog initialized: {'yes' if initialized else 'no'}")

    if initialized:
        # Hooks status
        active = _hooks_active(root)
        if active:
            click.echo("hooks active:")
            click.echo("  claude  ✓  (.claude/settings.json)")
        else:
            click.echo("hooks active: no")

        # Sessions
        sessions_dir = agentlog_dir / "sessions"
        count = 0
        total_size = 0
        if sessions_dir.is_dir():
            for p in sessions_dir.glob("*.jsonl"):
                count += 1
                total_size += p.stat().st_size
        click.echo(f"sessions: {count}  ({_format_size(total_size)})")

        # Config
        local_config = agentlog_dir / "config.json"
        if local_config.is_file():
            click.echo(f"config: {local_config.relative_to(root)}")
        else:
            click.echo("config: (none)")

        # Gitignore
        gitignore_path = root / ".gitignore"
        in_gitignore = False
        if gitignore_path.is_file():
            try:
                lines = gitignore_path.read_text(encoding="utf-8").splitlines()
                in_gitignore = ".agentlog/" in lines
            except Exception:
                pass
        click.echo(f"gitignore: {'yes' if in_gitignore else 'no'}")
    else:
        click.echo("Run 'agentlog init' to initialize.")
