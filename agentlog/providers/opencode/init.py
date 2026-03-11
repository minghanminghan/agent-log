"""OpenCode init — write the agentlog TypeScript plugin to .opencode/plugins/."""

import shutil
import sys
from pathlib import Path

import click


def detect(cwd: Path) -> bool:
    return (cwd / ".opencode").is_dir() or shutil.which("opencode") is not None


def init(cwd: Path) -> None:
    """Write the agentlog TypeScript plugin to .opencode/plugins/."""
    plugins_dir = cwd / ".opencode" / "plugins"
    try:
        plugins_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        click.echo(f"Error: could not create {plugins_dir}: {e}", err=True)
        sys.exit(1)

    plugin_dest = plugins_dir / "agentlog.ts"

    try:
        from importlib.resources import files
        plugin_src = files("agentlog.plugins").joinpath("agentlog.ts").read_text(encoding="utf-8")
    except Exception as e:
        click.echo(f"Error: could not read agentlog plugin asset: {e}", err=True)
        sys.exit(1)

    if plugin_dest.is_file() and plugin_dest.read_text(encoding="utf-8") == plugin_src:
        click.echo("Plugin already up to date (.opencode/plugins/agentlog.ts)")
        return

    try:
        plugin_dest.write_text(plugin_src, encoding="utf-8")
    except OSError as e:
        click.echo(f"Error: could not write plugin file {plugin_dest}: {e}", err=True)
        sys.exit(1)

    click.echo("Plugin written (.opencode/plugins/agentlog.ts)")
