"""Provider registries — single place to add a new coding agent provider."""

from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from agentlog.providers.claude import hooks as _claude_hooks
from agentlog.providers.claude import init as _claude_init
from agentlog.providers.claude import stop as _claude_stop
from agentlog.providers.claude import status as _claude_status
from agentlog.providers.opencode import hooks as _opencode_hooks
from agentlog.providers.opencode import init as _opencode_init
from agentlog.providers.opencode import stop as _opencode_stop
from agentlog.providers.opencode import status as _opencode_status


def _extract_claude(
    transcript_path: str, session_id: str, since_t: Optional[datetime]
) -> List[str]:
    return _claude_hooks.extract_assistant_turns(transcript_path, since_t)


def _extract_opencode(
    transcript_path: str, session_id: str, since_t: Optional[datetime]
) -> List[str]:
    return _opencode_hooks.extract_assistant_turns(transcript_path, session_id, since_t)


# names
PROVIDERS = ["claude", "opencode"]

# callable(transcript_path, session_id, since_t) -> List[str]
EXTRACTORS: dict[str, Callable[[str, str, Optional[datetime]], List[str]]] = {
    "claude": _extract_claude,
    "opencode": _extract_opencode,
}

# callable(cwd) -> bool
DETECTORS: dict[str, Callable[[Path], bool]] = {
    "claude": _claude_init.detect,
    "opencode": _opencode_init.detect,
}

# callable(cwd) -> None  (claude returns int but signature is compatible)
INITIALIZERS: dict[str, Callable[[Path], None]] = {
    "claude": _claude_init.init,
    "opencode": _opencode_init.init,
}

# callable(cwd) -> None
STOPPERS: dict[str, Callable[[Path], None]] = {
    "claude": _claude_stop.stop,
    "opencode": _opencode_stop.stop,
}

# callable(cwd) -> bool
STATUS_CHECKERS: dict[str, Callable[[Path], bool]] = {
    "claude": _claude_status.hooks_active,
    "opencode": _opencode_status.hooks_active,
}

# Human-readable hook location per provider (for status display)
LOCATIONS: dict[str, str] = {
    "claude": _claude_status.LOCATION,
    "opencode": _opencode_status.LOCATION,
}
