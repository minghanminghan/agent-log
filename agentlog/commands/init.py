"""agentlog init command."""

import json
import shutil
import sys
from pathlib import Path

import click

from agentlog import config as config_mod
from agentlog.providers import DETECTORS, INITIALIZERS


def _detect_agents(cwd: Path) -> list:
    """Auto-detect supported agents by checking for agent directories/binaries."""
    return [name for name, detect in DETECTORS.items() if detect(cwd)]


@click.command("init")
@click.option("--agent", default=None, help="Force a specific agent (claude, opencode).")
def init(agent):
    """Initialize agentlog in the current directory."""
    cwd = Path.cwd()

    # 1. Create .agentlog/sessions/
    agentlog_dir = cwd / ".agentlog"
    sessions_dir = agentlog_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # 2. Copy global config to local if not present
    local_config_path = agentlog_dir / "config.json"
    if not local_config_path.is_file():
        global_config_path = Path.home() / ".agentlog" / "config.json"
        if global_config_path.is_file():
            shutil.copy2(global_config_path, local_config_path)
        else:
            with open(local_config_path, "w", encoding="utf-8") as f:
                json.dump(config_mod.DEFAULT_CONFIG, f, indent=2)
                f.write("\n")

    # 3. Agent detection
    if agent is not None:
        agent_lower = agent.lower()
        if agent_lower not in INITIALIZERS:
            known = ", ".join(f"'{k}'" for k in INITIALIZERS)
            click.echo(
                f"Error: unknown agent '{agent}'. Expected one of: {known}.",
                err=True,
            )
            sys.exit(1)
        active_agents = [agent_lower]
        supported_agents = [agent_lower]
    else:
        supported_agents = _detect_agents(cwd)
        if not supported_agents:
            known = ", ".join(f"'agentlog init --agent {k}'" for k in INITIALIZERS)
            click.echo(
                f"Error: no supported coding agent detected.\n"
                f"Run {known} to force.",
                err=True,
            )
            sys.exit(1)
        active_agents = list(supported_agents)

    # 4. Update config with supported/active lists
    cfg_data = {}
    if local_config_path.is_file():
        try:
            with open(local_config_path, encoding="utf-8") as f:
                cfg_data = json.load(f)
        except Exception:
            cfg_data = {}
    cfg_data["supported"] = supported_agents
    cfg_data["active"] = active_agents
    with open(local_config_path, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
        f.write("\n")

    # 5. Per-agent init
    for ag in active_agents:
        click.echo(f"Detected: {ag}")
        INITIALIZERS[ag](cwd)

    # 6. Gitignore
    cfg = config_mod.load_config(cwd)
    gitignore_updated = False
    if cfg.get("gitignore", True):
        gitignore_path = cwd / ".gitignore"
        entry = ".agentlog/"
        if gitignore_path.is_file():
            content = gitignore_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            if entry not in lines:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    if content and not content.endswith("\n"):
                        f.write("\n")
                    f.write(entry + "\n")
                gitignore_updated = True
        else:
            gitignore_path.write_text(entry + "\n", encoding="utf-8")
            gitignore_updated = True

    # 7. Print status
    click.echo("Initialized .agentlog/")
    if gitignore_updated:
        click.echo("Added .agentlog/ to .gitignore")
