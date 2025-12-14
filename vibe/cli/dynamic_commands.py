from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DynamicCommandMetadata:
    """Metadata extracted from a command markdown file."""

    name: str
    aliases: frozenset[str]
    description: str
    content: str
    source: str  # "project" or "user"
    subdirectory: str | None = None  # Subdirectory path if organized


class DynamicCommandLoader:
    """Loads dynamic commands from markdown files in a commands directory."""

    def __init__(self, commands_dir: Path, source: str = "user") -> None:
        """Initialize the command loader.

        Args:
            commands_dir: Path to the directory containing command markdown files
            source: Either "project" or "user" to indicate command source
        """
        self.commands_dir = commands_dir
        self.source = source

    def load_commands(self) -> dict[str, DynamicCommandMetadata]:
        """Load all commands from the commands directory.

        Returns:
            Dictionary mapping command names to their metadata.
        """
        if not self.commands_dir.exists():
            return {}

        commands = {}
        # Use rglob to find all .md files including in subdirectories
        for md_file in self.commands_dir.rglob("*.md"):
            # Skip README files
            if md_file.stem.upper() == "README":
                continue

            if metadata := self._parse_command_file(md_file):
                commands[metadata.name] = metadata

        return commands

    def _parse_command_file(self, file_path: Path) -> DynamicCommandMetadata | None:
        """Parse a markdown command file to extract metadata.

        Expected format:
        ---
        name: command-name
        aliases: /cmd, /command
        description: Description of the command
        ---

        Command content goes here...

        Args:
            file_path: Path to the markdown file

        Returns:
            DynamicCommandMetadata if successful, None otherwise
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract frontmatter if present
            frontmatter_match = re.match(
                r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL
            )

            if frontmatter_match:
                frontmatter, body = frontmatter_match.groups()
                metadata = self._parse_frontmatter(frontmatter)
                metadata["content"] = body.strip()
            else:
                # No frontmatter, use filename as name
                metadata = {
                    "name": file_path.stem,
                    "aliases": frozenset([f"/{file_path.stem}"]),
                    "description": f"Custom command: {file_path.stem}",
                    "content": content.strip(),
                }

            # Ensure name exists
            if "name" not in metadata:
                metadata["name"] = file_path.stem

            # Ensure aliases is a frozenset
            if "aliases" not in metadata or not metadata["aliases"]:
                metadata["aliases"] = frozenset([f"/{metadata['name']}"])

            # Ensure description exists
            if "description" not in metadata:
                metadata["description"] = f"Custom command: {metadata['name']}"

            # Add source information
            metadata["source"] = self.source

            # Detect subdirectory
            relative_path = file_path.relative_to(self.commands_dir)
            if len(relative_path.parts) > 1:
                # File is in a subdirectory
                metadata["subdirectory"] = str(relative_path.parent)
            else:
                metadata["subdirectory"] = None

            return DynamicCommandMetadata(**metadata)

        except Exception:
            # Skip files that can't be parsed
            return None

    def _parse_frontmatter(self, frontmatter: str) -> dict:
        """Parse YAML-like frontmatter.

        Args:
            frontmatter: The frontmatter string

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "aliases":
                    # Parse comma-separated aliases
                    aliases = [
                        alias.strip() for alias in value.split(",") if alias.strip()
                    ]
                    # Ensure all aliases start with /
                    aliases = [
                        alias if alias.startswith("/") else f"/{alias}"
                        for alias in aliases
                    ]
                    metadata[key] = frozenset(aliases)
                else:
                    metadata[key] = value

        return metadata
