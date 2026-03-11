"""Claude Code init — register hooks in .claude/settings.json."""

import json
import shutil
from pathlib import Path

import click

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


def detect(cwd: Path) -> bool:
    return (cwd / ".claude").is_dir()


def init(cwd: Path) -> int:
    """Register Claude Code hooks in .claude/settings.json. Returns number added."""
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

    if hooks_added > 0:
        click.echo("Registered directory-scope hooks")
    else:
        click.echo("Already registered hooks")

    return hooks_added
