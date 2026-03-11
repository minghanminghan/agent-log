"""OpenCode stop — remove the agentlog plugin from .opencode/plugins/."""

from pathlib import Path

import click

_PLUGIN_PATH = Path(".opencode") / "plugins" / "agentlog.ts"


def stop(cwd: Path) -> None:
    """Remove the agentlog plugin from .opencode/plugins/."""
    plugin_path = cwd / _PLUGIN_PATH
    if not plugin_path.is_file():
        click.echo("No .opencode/plugins/agentlog.ts found, nothing to do.")
        return
    plugin_path.unlink()
    click.echo("agentlog plugin removed (.opencode/plugins/agentlog.ts)")
    click.echo(".agentlog/ directory left intact.")
