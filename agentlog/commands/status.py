"""agentlog status command."""

from pathlib import Path

import click

from agentlog import repo
from agentlog import config as config_mod
from agentlog.providers import STATUS_CHECKERS, LOCATIONS


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
    root: Path | None = repo.find_root(cwd)

    agentlog_dir = (root / ".agentlog") if root else (cwd / ".agentlog")
    initialized = root is not None and agentlog_dir.is_dir()

    click.echo(f"agentlog initialized: {'yes' if initialized else 'no'}")

    if initialized:
        cfg = config_mod.load_config(root)
        active_agents = cfg.get("active", [])
        supported_agents = cfg.get("supported", [])

        hook_lines = []
        for ag in supported_agents:
            is_active = ag in active_agents
            checker = STATUS_CHECKERS.get(ag)
            if checker is None:
                hook_lines.append(f"  {ag}  (unknown agent, skipped)")
                continue

            present = checker(root)
            location = LOCATIONS.get(ag, "")

            if not is_active:
                hook_lines.append(f"  {ag}  (disabled)")
            elif present:
                hook_lines.append(f"  {ag}: hook active at {location}")
            else:
                hook_lines.append(f"  {ag}: hook missing — re-run agentlog init")

        if hook_lines:
            click.echo("hooks active:")
            for line in hook_lines:
                click.echo(line)
        else:
            click.echo("hooks active: None")

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
