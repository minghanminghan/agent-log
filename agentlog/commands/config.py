"""agentlog config command group."""

import json
from pathlib import Path

import click

from agentlog.config import DEFAULT_CONFIG


@click.group("config")
def config_cmd():
    """Manage agentlog configuration."""
    pass


@config_cmd.command("init")
def config_init():
    """Write ~/.agentlog/config.json with defaults if it does not exist."""
    config_dir = Path.home() / ".agentlog"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"

    if config_path.is_file():
        click.echo(f"Config already exists: {config_path}")
        return

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
        f.write("\n")

    click.echo(f"✓ Created: {config_path}")
