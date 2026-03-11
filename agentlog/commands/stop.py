"""agentlog stop command — remove hook entries from .claude/settings.json."""

import json
from pathlib import Path

import click

_AGENTLOG_COMMANDS = {
    "agentlog hook user-prompt",
    "agentlog hook pre-tool",
    "agentlog hook post-tool",
    "agentlog hook stop",
}


def _is_agentlog_hook(command: str) -> bool:
    return command in _AGENTLOG_COMMANDS


def _filter_entries(entries: list) -> list:
    """Remove hook entries whose command matches agentlog hook *."""
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        hooks = entry.get("hooks", [])
        filtered_hooks = [
            h for h in hooks
            if not _is_agentlog_hook(h.get("command", ""))
        ]
        if filtered_hooks:
            new_entry = dict(entry)
            new_entry["hooks"] = filtered_hooks
            result.append(new_entry)
        elif not hooks:
            # No hooks key, keep as-is
            result.append(entry)
        # else: all hooks were agentlog — drop the entry
    return result


@click.command("stop")
def stop():
    """Remove agentlog hooks from .claude/settings.json."""
    cwd = Path.cwd()
    settings_path = cwd / ".claude" / "settings.json"

    if not settings_path.is_file():
        click.echo("No .claude/settings.json found — nothing to do.")
        return

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except Exception as e:
        click.echo(f"Error reading .claude/settings.json: {e}", err=True)
        return

    hooks_section = settings.get("hooks", {})
    if not hooks_section:
        click.echo("No hooks found — nothing to do.")
        return

    new_hooks = {}
    for event, entries in hooks_section.items():
        if not isinstance(entries, list):
            new_hooks[event] = entries
            continue
        filtered = _filter_entries(entries)
        if filtered:
            new_hooks[event] = filtered
        # Drop empty arrays

    settings["hooks"] = new_hooks
    if not new_hooks:
        del settings["hooks"]

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    click.echo("✓ agentlog hooks removed from .claude/settings.json")
    click.echo("  .agentlog/ directory left intact.")
