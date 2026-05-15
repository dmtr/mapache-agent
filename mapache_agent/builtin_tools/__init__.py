"""Built-in skill management tools always available to every agent.

These tools are injected into every agent's tool schema, without requiring
any external definition.

Sub-modules:
- ``skill_tools``  — list/read/execute/create/validate skills
- ``memory_tools`` — FTS5 search and recall over past messages
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mapache_agent.builtin_tools.memory_tools import MEMORY_SCHEMAS, get_memory_schemas
from mapache_agent.builtin_tools.skill_tools import (
    SKILL_SCHEMAS,
    _valid_skill_name,
    create_skill,
    execute_skill,
    list_skills,
    read_skill,
    validate_skill,
)

if TYPE_CHECKING:
    from mapache_agent.skill_registry import SkillRegistry

BUILTIN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "list_skills",
        "read_skill",
        "execute_skill",
        "create_skill",
        "validate_skill",
        "search_user_memory",
        "search_agent_memory",
        "get_recent_messages",
    }
)

BUILTIN_SCHEMAS: list[dict[str, Any]] = SKILL_SCHEMAS


def get_builtin_tools(
    skills_dir: str,
    memory: Any = None,
    disabled: frozenset[str] = frozenset(),
    tool_timeout: int = 600,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    """Return a name → callable mapping for all built-in tools.

    Each callable accepts only the LLM-provided arguments; ``skills_dir``,
    ``registry``, and ``memory`` are pre-bound via closure.  Tools whose names
    appear in *disabled* are omitted.

    ``execute_skill``, ``create_skill``, and ``validate_skill`` return
    coroutines and must be awaited by the caller.
    """
    tools: dict[str, Any] = {
        "list_skills": lambda **_kw: list_skills(skills_dir),
        "read_skill": lambda name, **_kw: read_skill(name, skills_dir),
        "execute_skill": lambda name, target, kwargs=None, **_kw: execute_skill(
            name, target, skills_dir, registry, kwargs, tool_timeout  # type: ignore[arg-type]
        ),
        "create_skill": lambda name, description, md_content, py_content=None, **_kw: create_skill(
            name, description, md_content, skills_dir, registry, py_content  # type: ignore[arg-type]
        ),
        "validate_skill": lambda name, **_kw: validate_skill(name, skills_dir, registry),  # type: ignore[arg-type]
    }
    if memory is not None:
        tools["search_user_memory"] = lambda query, limit=10, from_date=None, to_date=None, **_kw: memory.search_user(query, limit, from_date, to_date)
        tools["search_agent_memory"] = lambda query, limit=10, from_date=None, to_date=None, **_kw: memory.search_agent(query, limit, from_date, to_date)
        tools["get_recent_messages"] = lambda limit=10, from_date=None, to_date=None, **_kw: memory.recent(limit, from_date, to_date)

    return {name: fn for name, fn in tools.items() if name not in disabled}


__all__ = [
    "BUILTIN_SCHEMAS",
    "BUILTIN_TOOL_NAMES",
    "MEMORY_SCHEMAS",
    "SKILL_SCHEMAS",
    "_valid_skill_name",
    "create_skill",
    "execute_skill",
    "get_builtin_tools",
    "get_memory_schemas",
    "list_skills",
    "read_skill",
    "validate_skill",
]
