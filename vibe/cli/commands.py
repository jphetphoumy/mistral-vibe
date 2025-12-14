from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vibe.cli.dynamic_commands import DynamicCommandLoader


@dataclass
class Command:
    aliases: frozenset[str]
    description: str
    handler: str
    exits: bool = False
    is_dynamic: bool = False
    content: str | None = None
    source: str | None = None  # "project", "user", or None for built-in
    subdirectory: str | None = None  # Subdirectory path if organized


class CommandRegistry:
    def __init__(self, excluded_commands: list[str] | None = None) -> None:
        if excluded_commands is None:
            excluded_commands = []
        self.commands = {
            "help": Command(
                aliases=frozenset(["/help", "/h"]),
                description="Show help message",
                handler="_show_help",
            ),
            "status": Command(
                aliases=frozenset(["/status", "/stats"]),
                description="Display agent statistics",
                handler="_show_status",
            ),
            "config": Command(
                aliases=frozenset(["/config", "/cfg", "/theme", "/model"]),
                description="Edit config settings",
                handler="_show_config",
            ),
            "reload": Command(
                aliases=frozenset(["/reload", "/r"]),
                description="Reload configuration from disk",
                handler="_reload_config",
            ),
            "clear": Command(
                aliases=frozenset(["/clear", "/reset"]),
                description="Clear conversation history",
                handler="_clear_history",
            ),
            "log": Command(
                aliases=frozenset(["/log", "/logpath"]),
                description="Show path to current interaction log file",
                handler="_show_log_path",
            ),
            "compact": Command(
                aliases=frozenset(["/compact", "/summarize"]),
                description="Compact conversation history by summarizing",
                handler="_compact_history",
            ),
            "exit": Command(
                aliases=frozenset(["/exit", "/quit", "/q"]),
                description="Exit the application",
                handler="_exit_app",
                exits=True,
            ),
        }

        for command in excluded_commands:
            self.commands.pop(command, None)

        self._build_alias_map()

    def _build_alias_map(self) -> None:
        """Build the alias to command name mapping."""
        self._alias_map = {}
        for cmd_name, cmd in self.commands.items():
            for alias in cmd.aliases:
                self._alias_map[alias] = cmd_name

    def load_dynamic_commands(
        self, project_commands_dir: Path, user_commands_dir: Path
    ) -> None:
        """Load dynamic commands from both project and user directories.

        Project commands take precedence over user commands with the same name.

        Args:
            project_commands_dir: Path to project-level commands (.vibe/commands)
            user_commands_dir: Path to user-level commands (~/.vibe/commands)
        """
        # Load user commands first
        user_loader = DynamicCommandLoader(user_commands_dir, source="user")
        user_commands = user_loader.load_commands()

        # Load project commands second (they override user commands)
        project_loader = DynamicCommandLoader(project_commands_dir, source="project")
        project_commands = project_loader.load_commands()

        # Combine commands with project taking precedence
        all_commands = {**user_commands, **project_commands}

        for cmd_metadata in all_commands.values():
            # Build description label based on source and subdirectory
            desc_label = ""
            if cmd_metadata.subdirectory:
                desc_label = f"({cmd_metadata.source}:{cmd_metadata.subdirectory})"
            else:
                desc_label = f"({cmd_metadata.source})"

            description_with_label = f"{cmd_metadata.description} {desc_label}"

            # Create a dynamic command
            self.commands[cmd_metadata.name] = Command(
                aliases=cmd_metadata.aliases,
                description=description_with_label,
                handler="_handle_dynamic_command",
                is_dynamic=True,
                content=cmd_metadata.content,
                source=cmd_metadata.source,
                subdirectory=cmd_metadata.subdirectory,
            )

        # Rebuild alias map to include new commands
        self._build_alias_map()

    def find_command(self, user_input: str) -> Command | None:
        cmd_name = self._alias_map.get(user_input.lower().strip())
        return self.commands.get(cmd_name) if cmd_name else None

    def get_help_text(self) -> str:
        lines: list[str] = [
            "### Keyboard Shortcuts",
            "",
            "- `Enter` Submit message",
            "- `Ctrl+J` / `Shift+Enter` Insert newline",
            "- `Escape` Interrupt agent or close dialogs",
            "- `Ctrl+C` Quit (or clear input if text present)",
            "- `Ctrl+O` Toggle tool output view",
            "- `Ctrl+T` Toggle todo view",
            "- `Shift+Tab` Toggle auto-approve mode",
            "",
            "### Special Features",
            "",
            "- `!<command>` Execute bash command directly",
            "- `@path/to/file/` Autocompletes file paths",
            "",
            "### Commands",
            "",
        ]

        for cmd in self.commands.values():
            aliases = ", ".join(f"`{alias}`" for alias in sorted(cmd.aliases))
            lines.append(f"- {aliases}: {cmd.description}")
        return "\n".join(lines)
