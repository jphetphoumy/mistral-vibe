from __future__ import annotations

import functools
import inspect
import re
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.config_path import GLOBAL_SKILLS_DIR, SKILLS_DIR
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)


class SkillMetadata(BaseModel):
    """Metadata for a skill loaded from markdown file."""

    name: str
    description: str
    content: str
    source: str  # "project" or "user"


class SkillToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class SkillArgs(BaseModel):
    skill: str = Field(description="The skill name (no arguments). E.g., \"pdf\" or \"xlsx\"")


class SkillResult(BaseModel):
    expanded_prompt: str = Field(description="The expanded skill prompt")


class Skill(BaseTool[SkillArgs, SkillResult, SkillToolConfig, BaseToolState]):
    description: ClassVar[str] = "Execute a skill within the main conversation"

    @classmethod
    @functools.lru_cache(maxsize=1)
    def get_tool_prompt(cls) -> str | None:
        """Override to dynamically inject available skills into the prompt.

        Note: This is cached, so skills are loaded once at startup. To refresh,
        restart the application or clear the cache with cls.get_tool_prompt.cache_clear().

        Returns:
            The skill tool prompt with dynamically loaded skills
        """
        # Get the base prompt from the markdown file
        # We bypass the parent's cached method to ensure we get fresh content
        try:
            class_file = inspect.getfile(cls)
            class_path = Path(class_file)
            prompt_dir = class_path.parent / "prompts"
            prompt_path = cls.prompt_path or prompt_dir / f"{class_path.stem}.md"
            base_prompt = prompt_path.read_text("utf-8")
        except (FileNotFoundError, TypeError, OSError):
            return None

        # Load all available skills
        skills = cls.load_skills()

        # Build the skills list
        if skills:
            skills_list = []
            for skill in sorted(skills.values(), key=lambda s: s.name):
                # Determine if it's gitignored (project skills are in .vibe which is gitignored)
                gitignored_tag = ", gitignored" if skill.source == "project" else ""
                skills_list.append(
                    f"<skill>\n"
                    f"<name>\n{skill.name}\n</name>\n"
                    f"<description>\n{skill.description} ({skill.source}{gitignored_tag})\n</description>\n"
                    f"<location>\n{skill.source}\n</location>\n"
                    f"</skill>"
                )
            skills_section = "\n".join(skills_list)
        else:
            skills_section = "<!-- No skills available -->"

        # Replace the placeholder comment with actual skills
        enhanced_prompt = base_prompt.replace(
            "<!-- Skills will be dynamically loaded from .vibe/skills and ~/.vibe/skills directories -->",
            skills_section,
        )

        return enhanced_prompt

    @staticmethod
    def load_skills() -> dict[str, SkillMetadata]:
        """Load all skills from both user and project directories.

        Project skills take precedence over user skills.

        Returns:
            Dictionary mapping skill names to their metadata
        """
        skills = {}

        # Load user skills first
        if GLOBAL_SKILLS_DIR.path.exists():
            user_skills = Skill._load_skills_from_dir(
                GLOBAL_SKILLS_DIR.path, source="user"
            )
            skills.update(user_skills)

        # Load project skills (they override user skills)
        if SKILLS_DIR.path.exists():
            project_skills = Skill._load_skills_from_dir(SKILLS_DIR.path, source="project")
            skills.update(project_skills)

        return skills

    @staticmethod
    def _load_skills_from_dir(skills_dir: Path, source: str) -> dict[str, SkillMetadata]:
        """Load skills from a specific directory.

        Args:
            skills_dir: Directory containing skill markdown files
            source: Either "project" or "user"

        Returns:
            Dictionary mapping skill names to their metadata
        """
        skills = {}

        # Only load files named SKILL.md
        for md_file in skills_dir.rglob("SKILL.md"):

            if metadata := Skill._parse_skill_file(md_file, source):
                skills[metadata.name] = metadata

        return skills

    @staticmethod
    def _parse_skill_file(file_path: Path, source: str) -> SkillMetadata | None:
        """Parse a markdown skill file to extract metadata.

        Expected format:
        ---
        name: skill-name
        description: Description of the skill
        ---

        Skill content/instructions go here...

        Args:
            file_path: Path to the markdown file
            source: Either "project" or "user"

        Returns:
            SkillMetadata if successful, None otherwise
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract frontmatter if present
            frontmatter_match = re.match(
                r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL
            )

            if frontmatter_match:
                frontmatter, body = frontmatter_match.groups()
                metadata = Skill._parse_frontmatter(frontmatter)
                metadata["content"] = body.strip()
            else:
                # No frontmatter, use filename as name
                metadata = {
                    "name": file_path.stem,
                    "description": f"Custom skill: {file_path.stem}",
                    "content": content.strip(),
                }

            # Ensure name exists
            if "name" not in metadata:
                metadata["name"] = file_path.stem

            # Ensure description exists
            if "description" not in metadata:
                metadata["description"] = f"Custom skill: {metadata['name']}"

            # Add source information
            metadata["source"] = source

            return SkillMetadata(**metadata)

        except Exception:
            # Skip files that can't be parsed
            return None

    @staticmethod
    def _parse_frontmatter(frontmatter: str) -> dict:
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
                metadata[key] = value

        return metadata

    async def run(self, args: SkillArgs) -> SkillResult:
        """Execute a skill by loading and returning its content.

        Args:
            args: Arguments containing the skill name

        Returns:
            SkillResult with the expanded skill prompt

        Raises:
            ToolError: If the skill is not found
        """
        # Load all available skills
        skills = Skill.load_skills()

        # Find the requested skill
        skill_name = args.skill.strip()
        if skill_name not in skills:
            available = ", ".join(sorted(skills.keys()))
            raise ToolError(
                f"Skill '{skill_name}' not found. Available skills: {available or 'none'}"
            )

        skill_metadata = skills[skill_name]
        return SkillResult(expanded_prompt=skill_metadata.content)
