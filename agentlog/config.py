"""Configuration loading and defaults."""

import json
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "log_tool_calls": True,
    "log_tool_results": False,
    "log_assistant_messages": True,
    "log_user_messages": True,
    "content_max_chars": -1,  # -1 = no cap; set to a positive integer to truncate
    "gitignore": True,
}


def load_config(repo_root: Path) -> dict:
    """Load and merge global and local agentlog configuration.

    Reads `~/.agentlog/config.json` (global defaults), then merges
    `.agentlog/config.json` (local overrides). Local keys win. Missing
    files are silently ignored. Parse errors emit a warning to stderr.
    All keys fall back to DEFAULT_CONFIG values.
    """
    config = dict(DEFAULT_CONFIG)

    global_config_path = Path.home() / ".agentlog" / "config.json"
    if global_config_path.is_file():
        try:
            with open(global_config_path, encoding="utf-8") as f:
                global_data = json.load(f)
            config.update(global_data)
        except json.JSONDecodeError as e:
            sys.stderr.write(
                f"agentlog: warning: could not parse global config "
                f"{global_config_path}: {e}\n"
            )
        except OSError as e:
            sys.stderr.write(
                f"agentlog: warning: could not read global config "
                f"{global_config_path}: {e}\n"
            )

    local_config_path = repo_root / ".agentlog" / "config.json"
    if local_config_path.is_file():
        try:
            with open(local_config_path, encoding="utf-8") as f:
                local_data = json.load(f)
            config.update(local_data)
        except json.JSONDecodeError as e:
            sys.stderr.write(
                f"agentlog: warning: could not parse local config "
                f"{local_config_path}: {e}\n"
            )
        except OSError as e:
            sys.stderr.write(
                f"agentlog: warning: could not read local config "
                f"{local_config_path}: {e}\n"
            )

    return config
