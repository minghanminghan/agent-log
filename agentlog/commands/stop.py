"""agentlog stop command — remove hook entries or plugins for a provider."""

from pathlib import Path

import click

from agentlog.providers import PROVIDERS, STOPPERS

STOP_OPTIONS = PROVIDERS + ["all"]

@click.command("stop")
@click.option(
    "--agent",
    type=click.Choice(STOP_OPTIONS, case_sensitive=False),
    default="claude",
    show_default=True,
    help="Agent to remove hooks for.",
)
def stop(agent):
    """Remove agentlog hooks or plugin for the specified agent."""
    cwd = Path.cwd()
    agent_lower = agent.lower()

    if agent_lower == "all":
        for stop_fn in STOPPERS.values():
            stop_fn(cwd)
    else:
        STOPPERS[agent_lower](cwd)
