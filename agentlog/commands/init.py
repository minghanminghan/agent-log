"""agentlog init command."""

import json
import shutil
import sys
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


def _detect_agents(cwd: Path) -> list:
    """Auto-detect supported agents by checking for agent directories/binaries."""
    detected = []
    if (cwd / ".claude").is_dir():
        detected.append("claude")
    if (cwd / ".opencode").is_dir() or shutil.which("opencode") is not None:
        detected.append("opencode")
    return detected


def _init_claude(cwd: Path) -> int:
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

    return hooks_added


def _init_opencode(cwd: Path) -> None:
    """Write the agentlog TypeScript plugin to .opencode/plugins/."""
    plugins_dir = cwd / ".opencode" / "plugins"
    try:
        plugins_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        click.echo(f"Error: could not create {plugins_dir}: {e}", err=True)
        sys.exit(1)

    plugin_dest = plugins_dir / "agentlog.ts"

    # Load plugin source from package assets
    try:
        from importlib.resources import files
        plugin_src = files("agentlog.plugins").joinpath("agentlog.ts").read_text(encoding="utf-8")
    except Exception as e:
        click.echo(f"Error: could not read agentlog plugin asset: {e}", err=True)
        sys.exit(1)

    if plugin_dest.is_file() and plugin_dest.read_text(encoding="utf-8") == plugin_src:
        click.echo("Plugin already up to date (.opencode/plugins/agentlog.ts)")
        return

    try:
        plugin_dest.write_text(plugin_src, encoding="utf-8")
    except OSError as e:
        click.echo(f"Error: could not write plugin file {plugin_dest}: {e}", err=True)
        sys.exit(1)

    click.echo("Plugin written (.opencode/plugins/agentlog.ts)")


@click.command("init")
@click.option("--agent", default=None, help="Force a specific agent (claude, opencode).")
def init(agent):
    """Initialize agentlog in the current directory."""
    cwd = Path.cwd()

    # 1. Create .agentlog/sessions/
    agentlog_dir = cwd / ".agentlog"
    sessions_dir = agentlog_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    # 
    # 2. Copy global config to local if not present
    local_config_path = agentlog_dir / "config.json"
    if not local_config_path.is_file():
        global_config_path = Path.home() / ".agentlog" / "config.json"
        if global_config_path.is_file():
            shutil.copy2(global_config_path, local_config_path)
        else:
            # Write defaults
            with open(local_config_path, "w", encoding="utf-8") as f:
                json.dump(config_mod.DEFAULT_CONFIG, f, indent=2)
                f.write("\n")

    # 3. Agent detection
    if agent is not None:
        agent_lower = agent.lower()
        if agent_lower not in ("claude", "opencode"):
            click.echo(
                f"Error: unknown agent '{agent}'. Expected 'claude' or 'opencode'.",
                err=True,
            )
            sys.exit(1)
        active_agents = [agent_lower]
        supported_agents = [agent_lower]
    else:
        supported_agents = _detect_agents(cwd)
        if not supported_agents:
            click.echo(
                "Error: no supported coding agent detected.\n"
                "Expected one of: Claude Code (.claude/), OpenCode (.opencode/ or 'opencode' on PATH).\n"
                "Run 'agentlog init --agent claude' or 'agentlog init --agent opencode' to force.",
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
        if ag == "claude":
            hooks_added = _init_claude(cwd)
            if hooks_added > 0:
                click.echo("Hooks registered (directory-scoped)")
            else:
                click.echo("Hooks already registered")
        elif ag == "opencode":
            _init_opencode(cwd)

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
