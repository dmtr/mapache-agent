"""Skill management tools: list_skills, read_skill, execute_skill, create_skill, validate_skill."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from mapache_agent.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

_VALID_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _valid_skill_name(name: str) -> bool:
    return bool(_VALID_SKILL_NAME_RE.fullmatch(name))


def _skill_description(md_path: Path) -> str:
    """Return the skill's one-line description from skill.md frontmatter, or a fallback."""
    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError:
        return "  (could not read)"
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(content[3:end].strip())
                if isinstance(fm, dict) and "description" in fm:
                    return f"  {fm['description']}"
            except Exception:
                pass
    return "  (no description)"


def list_skills(skills_dir: str) -> str:
    """List all available skills with their names and descriptions."""
    path = Path(skills_dir)
    if not path.exists():
        return "No skills found (directory does not exist)"
    skill_dirs = sorted(p for p in path.iterdir() if p.is_dir() and (p / "skill.md").exists())
    if not skill_dirs:
        return "No skills found"
    entries = []
    for sd in skill_dirs:
        desc = _skill_description(sd / "skill.md")
        entry = f"{sd.name}:{desc}"
        if (sd / "skill.py").exists():
            entry += "  [has tools]"
        entries.append(entry)
    return "\n\n".join(entries)


def read_skill(name: str, skills_dir: str) -> str:
    """Read a skill's instructions (skill.md only)."""
    if not _valid_skill_name(name):
        return f"Error: invalid skill name {name!r}. Use letters, numbers, hyphens, underscores, and dots only."
    skill_dir = Path(skills_dir) / name
    md_path = skill_dir / "skill.md"
    if not skill_dir.exists():
        return f"Skill '{name}' not found in {skills_dir}"
    if not md_path.exists():
        return f"Skill '{name}' is missing skill.md"
    try:
        return md_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error: could not read skill.md: {e}"


def _format_param_help(meta: Any) -> str:
    """Format a one-line param description for error messages."""
    default_str = "" if meta.required else f"  [default: {meta.default!r}]"
    req_str = "  [required]" if meta.required else ""
    desc_str = f"  — {meta.description}" if meta.description else ""
    return f"  {meta.name}: {meta.json_type}{req_str}{default_str}{desc_str}"


async def execute_skill(
    name: str,
    target: str,
    skills_dir: str,
    registry: SkillRegistry,
    kwargs: dict[str, Any] | None = None,
    timeout: int = 600,
) -> str:
    """Run *target* in skill *name* using keyword arguments."""
    if not _valid_skill_name(name):
        return f"Error: invalid skill name {name!r}. Use letters, numbers, hyphens, underscores, and dots only."
    skill_dir = Path(skills_dir) / name
    if not skill_dir.exists() or not (skill_dir / "skill.md").exists():
        return f"Skill '{name}' not found in {skills_dir}"
    py_path = skill_dir / "skill.py"
    if not py_path.exists():
        return f"Skill '{name}' has no skill.py"

    entry = await registry.get_entry(name)
    if entry is None:
        # Not yet in registry — try loading it now
        entry = await registry.load_or_add(name, skills_dir)
    if entry is None or not entry.valid:
        reason = entry.reject_reason if entry else "unknown"
        return f"Error: skill '{name}' is not valid: {reason}"

    tool_meta = entry.tools.get(target)
    if tool_meta is None:
        available = ", ".join(entry.tools) or "(none)"
        return f"Error: skill '{name}' has no target '{target}'. Available: {available}"

    # Validate kwargs against ToolMeta
    kw = kwargs or {}
    missing = [p for p in tool_meta.params if p.required and p.name not in kw]
    if missing:
        lines = [f"Error: missing required argument(s) for '{name}/{target}':"]
        for p in missing:
            lines.append(f"  {p.name}: {p.json_type}  — {p.description}" if p.description else f"  {p.name}: {p.json_type}")
        lines.append(f"\n'{target}' expects:")
        for p in tool_meta.params:
            lines.append(_format_param_help(p))
        return "\n".join(lines)

    # Build final kwargs: fill defaults for missing optional params
    final_kw: dict[str, Any] = {}
    for p in tool_meta.params:
        if p.name in kw:
            final_kw[p.name] = kw[p.name]
        elif not p.required and p.default is not None:
            final_kw[p.name] = p.default

    loop = asyncio.get_event_loop()
    fn = tool_meta.fn
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: fn(**final_kw)),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return f"Error: execute_skill '{name}/{target}' exceeded {timeout}s timeout"
    except Exception as e:
        logger.error("execute_skill '%s/%s' raised: %s", name, target, e)
        return f"Error: {e}"

    return str(result) if result is not None else "OK. Execution succeeded with no output."


def _write_no_symlink(path: Path, content: str) -> None:
    """Write *content* to *path*, refusing symlink destinations."""
    if path.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {path}")
    path.write_text(content, encoding="utf-8")


async def create_skill(
    name: str,
    description: str,
    md_content: str,
    skills_dir: str,
    registry: SkillRegistry,
    py_content: str | None = None,
) -> str:
    """Create or overwrite a skill directory with skill.md and optional skill.py."""
    if not _valid_skill_name(name):
        return f"Error: invalid skill name {name!r}. Use letters, numbers, hyphens, underscores, and dots only."

    skill_dir = Path(skills_dir) / name
    md_path = skill_dir / "skill.md"
    py_path = skill_dir / "skill.py"

    if md_path.is_symlink():
        return f"Error: refusing to overwrite symlink: {md_path}"
    if py_content and py_path.is_symlink():
        return f"Error: refusing to overwrite symlink: {py_path}"

    skill_dir.mkdir(parents=True, exist_ok=True)

    if not md_content.strip().startswith("---"):
        md_with_fm = f'---\ndescription: "{description}"\n---\n\n{md_content}'
    else:
        md_with_fm = md_content

    try:
        _write_no_symlink(md_path, md_with_fm)
    except (OSError, ValueError) as e:
        return f"Error: could not write skill.md: {e}"

    if py_content:
        try:
            _write_no_symlink(py_path, py_content)
        except (OSError, ValueError) as e:
            return f"Error: could not write skill.py: {e}"
        # Auto-validate after writing
        entry = await registry.load_or_add(name, skills_dir)
        if entry is None or not entry.valid:
            reason = entry.reject_reason if entry else "unknown"
            py_path.unlink(missing_ok=True)
            return f"Error: skill.py rejected: {reason}"
        return f"Created skill '{name}' at {skill_dir} ({len(entry.tools)} tool(s))"

    return f"Created skill '{name}' at {skill_dir} (no tools)"


async def validate_skill(name: str, skills_dir: str, registry: SkillRegistry) -> str:
    """Validate a skill: checks skill.md exists and runs LLM security check on skill.py."""
    if not _valid_skill_name(name):
        return f"Error: invalid skill name {name!r}. Use letters, numbers, hyphens, underscores, and dots only."
    skill_dir = Path(skills_dir) / name
    md_path = skill_dir / "skill.md"
    if not skill_dir.exists():
        return f"Skill '{name}' not found in {skills_dir}"
    if not md_path.exists():
        return f"Skill '{name}' is missing skill.md"
    py_path = skill_dir / "skill.py"
    if not py_path.exists():
        return f"OK — {skill_dir} (skill.md only, no tools)"
    entry = await registry.load_or_add(name, skills_dir)
    if entry is None or not entry.valid:
        reason = entry.reject_reason if entry else "unknown"
        return f"INVALID: {reason}"
    return f"OK — {skill_dir} ({len(entry.tools)} tool(s) valid)"


SKILL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills with their names and descriptions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "Read a skill's instructions from skill.md. Call this first to learn what targets and parameters are available before calling execute_skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The skill name (directory name)."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_skill",
            "description": (
                "Run a target in a skill's skill.py. "
                "Only usable when the skill has a skill.py file with @target functions. "
                "Call read_skill first to learn what targets and parameters are available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The skill name (directory name)."},
                    "target": {"type": "string", "description": "The target function name to run."},
                    "kwargs": {
                        "type": "object",
                        "description": "Keyword arguments to pass to the target function.",
                        "additionalProperties": True,
                    },
                },
                "required": ["name", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_skill",
            "description": (
                "Create a new skill or overwrite an existing one. "
                "A skill consists of skill.md (instructions) and optionally skill.py (tools). "
                "skill.py uses @target decorated functions. After creation, skill.py is automatically validated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name (letters, numbers, hyphens, underscores, dots).",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-line description shown in list_skills.",
                    },
                    "md_content": {
                        "type": "string",
                        "description": "Full content of skill.md (instructions for the agent).",
                    },
                    "py_content": {
                        "type": "string",
                        "description": (
                            "Optional: content of skill.py with @target decorated functions. "
                            "Import target with: from mapache_agent import target"
                        ),
                    },
                },
                "required": ["name", "description", "md_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_skill",
            "description": "Validate a skill: checks skill.md exists and runs LLM security check on skill.py if present.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The skill name (directory name)."},
                },
                "required": ["name"],
            },
        },
    },
]
