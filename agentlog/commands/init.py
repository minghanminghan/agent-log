"""agentlog init command."""

import json
from pathlib import Path

import click

from agentlog import config as config_mod

AGENTLOG_HOOK_ENTRIES = {
    "UserPromptSubmit": [
        {
            "hooks": [
                {"type": "command", "command": "agentlog hook user-prompt"}
            ]
        }
    ],
    "PreToolUse": [
        {
            "matcher": "",
            "hooks": [
                {"type": "command", "command": "agentlog hook pre-tool"}
            ],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "",
            "hooks": [
                {"type": "command", "command": "agentlog hook post-tool"}
            ],
        }
    ],
    "Stop": [
        {
            "hooks": [
                {"type": "command", "command": "agentlog hook stop"}
            ]
        }
    ],
}

AGENTLOG_README = """\
# .agentlog

This directory contains session logs captured by [agentlog](https://github.com/your-org/agentlog).

Each `.jsonl` file in `sessions/` records one Claude Code conversation: the prompts, tool calls,
and assistant responses. Files are append-only and named `<timestamp>_<session-id>.jsonl`.

You can browse them with:

    agentlog log
    agentlog show <session-id>

See `config.json` for per-repo settings.
"""


def _command_in_settings(settings: dict, command: str) -> bool:
    """Return True if a hook command string is already present in settings."""
    hooks_section = settings.get("hooks", {})
    for _event, entries in hooks_section.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for h in entry.get("hooks", []):
                if h.get("command") == command:
                    return True
    return False


@click.command("init")
def init():
    """Initialize agentlog in the current directory."""
    cwd = Path.cwd()

    # 1. Create .agentlog/sessions/
    agentlog_dir = cwd / ".agentlog"
    sessions_dir = agentlog_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # 2. Write README.md
    readme_path = agentlog_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(AGENTLOG_README, encoding="utf-8")

    # 3. Copy global config to local if not present
    local_config_path = agentlog_dir / "config.json"
    if not local_config_path.is_file():
        global_config_path = Path.home() / ".agentlog" / "config.json"
        if global_config_path.is_file():
            import shutil
            shutil.copy2(global_config_path, local_config_path)
        else:
            # Write defaults
            with open(local_config_path, "w", encoding="utf-8") as f:
                json.dump(config_mod.DEFAULT_CONFIG, f, indent=2)
                f.write("\n")

    # 4. Merge hook entries into .claude/settings.json
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_path = claude_dir / "settings.json"

    if settings_path.is_file():
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    else:
        settings = {}

    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks_section = settings["hooks"]
    hooks_added = 0

    for event, new_entries in AGENTLOG_HOOK_ENTRIES.items():
        if event not in hooks_section:
            hooks_section[event] = []
        for new_entry in new_entries:
            # Check if the command is already registered
            cmd = new_entry["hooks"][0]["command"]
            already_present = False
            for existing_entry in hooks_section[event]:
                for h in existing_entry.get("hooks", []):
                    if h.get("command") == cmd:
                        already_present = True
                        break
                if already_present:
                    break
            if not already_present:
                hooks_section[event].append(new_entry)
                hooks_added += 1

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    # 5. Gitignore
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

    # 6. Print status
    click.echo("✓ Detected: claude")
    if hooks_added > 0:
        click.echo("✓ Hooks registered (directory-scoped)")
    else:
        click.echo("✓ Hooks already registered")
    click.echo("✓ Initialized .agentlog/")
    if gitignore_updated:
        click.echo("✓ Added .agentlog/ to .gitignore")
