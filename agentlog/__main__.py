"""agentlog CLI entry point."""

import click

from agentlog.commands.hook import hook
from agentlog.commands.init import init
from agentlog.commands.stop import stop
from agentlog.commands.log import log
from agentlog.commands.show import show
from agentlog.commands.search import search
from agentlog.commands.status import status
from agentlog.commands.stats import stats
from agentlog.commands.prune import prune
from agentlog.commands.export import export
from agentlog.commands.config import config_cmd


@click.group()
def cli():
    """agentlog — session logging for Claude Code."""
    pass


cli.add_command(hook)
cli.add_command(init)
cli.add_command(stop)
cli.add_command(log)
cli.add_command(show)
cli.add_command(search)
cli.add_command(status)
cli.add_command(stats)
cli.add_command(prune)
cli.add_command(export)
cli.add_command(config_cmd)


def main():
    cli()


if __name__ == "__main__":
    main()
