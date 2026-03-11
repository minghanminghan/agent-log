"""Claude Code status check."""

from pathlib import Path

_AGENTLOG_COMMANDS = {
    "agentlog hook user-prompt",
    "agentlog hook pre-tool",
    "agentlog hook post-tool",
    "agentlog hook stop",
}

LOCATION = ".claude/settings.json"


def hooks_active(cwd: Path) -> bool:
    """Return True if agentlog hooks are registered in .claude/settings.json."""
    import json
    settings_path = cwd / ".claude" / "settings.json"
    if not settings_path.is_file():
        return False
    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
        hooks = settings.get("hooks", {})
        for event, entries in hooks.items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    if h.get("command") in _AGENTLOG_COMMANDS:
                        return True
    except Exception:
        pass
    return False
