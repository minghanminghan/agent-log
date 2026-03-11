"""OpenCode status check."""

from pathlib import Path

LOCATION = ".opencode/plugins/agentlog.ts"


def hooks_active(cwd: Path) -> bool:
    """Return True if the agentlog plugin is present in .opencode/plugins/."""
    return (cwd / ".opencode" / "plugins" / "agentlog.ts").is_file()
