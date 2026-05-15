"""Tests for mapache_agent/builtin_tools — skill tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from mapache_agent.builtin_tools import (
    BUILTIN_SCHEMAS,
    _valid_skill_name,
    create_skill,
    execute_skill,
    get_builtin_tools,
    list_skills,
    read_skill,
    validate_skill,
)
from mapache_agent.skill_registry import SkillRegistry

_VALID_PY = """\
from mapache_agent import target

@target
def read_file(path: str) -> str:
    \"\"\"Read the contents of a file.

    :param path: The file path
    \"\"\"
    return open(path).read()

@target
def write_file(path: str, content: str) -> str:
    \"\"\"Write content to a file.

    :param path: The destination path
    :param content: The content to write
    \"\"\"
    open(path, "w").write(content)
    return f"Written: {path}"
"""


def _mock_registry(valid: bool = True) -> SkillRegistry:
    registry = SkillRegistry(model="test-model")
    return registry


# ── _valid_skill_name ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["file-search", "skill1", "my.skill", "A_B"])
def test_valid_skill_name_accepts_valid(name):
    assert _valid_skill_name(name) is True


@pytest.mark.parametrize("name", ["", "-bad", "../escape", "has space", "has/slash"])
def test_valid_skill_name_rejects_invalid(name):
    assert _valid_skill_name(name) is False


# ── list_skills ───────────────────────────────────────────────────────────────


def test_list_skills_missing_dir(tmp_path):
    result = list_skills(str(tmp_path / "nonexistent"))
    assert "No skills found" in result


def test_list_skills_empty_dir(tmp_path):
    result = list_skills(str(tmp_path))
    assert "No skills found" in result


def test_list_skills_returns_skills(tmp_path):
    (tmp_path / "search").mkdir()
    (tmp_path / "search" / "skill.md").write_text('---\ndescription: "Searches files by pattern."\n---\n')
    (tmp_path / "writer").mkdir()
    (tmp_path / "writer" / "skill.md").write_text('---\ndescription: "Writes and edits files."\n---\n')
    result = list_skills(str(tmp_path))
    assert "search:" in result
    assert "Searches files by pattern." in result
    assert "writer:" in result
    assert "Writes and edits files." in result


def test_list_skills_sorted(tmp_path):
    (tmp_path / "zzz").mkdir()
    (tmp_path / "zzz" / "skill.md").write_text('---\ndescription: "Z skill."\n---\n')
    (tmp_path / "aaa").mkdir()
    (tmp_path / "aaa" / "skill.md").write_text('---\ndescription: "A skill."\n---\n')
    result = list_skills(str(tmp_path))
    assert result.index("aaa:") < result.index("zzz:")


def test_list_skills_marks_has_tools(tmp_path):
    (tmp_path / "rich").mkdir()
    (tmp_path / "rich" / "skill.md").write_text('---\ndescription: "Has tools."\n---\n')
    (tmp_path / "rich" / "skill.py").write_text(_VALID_PY)
    result = list_skills(str(tmp_path))
    assert "[has tools]" in result


def test_list_skills_no_description_fallback(tmp_path):
    (tmp_path / "bare").mkdir()
    (tmp_path / "bare" / "skill.md").write_text("Just some text\n")
    result = list_skills(str(tmp_path))
    assert "(no description)" in result


# ── read_skill ────────────────────────────────────────────────────────────────


def test_read_skill_not_found(tmp_path):
    result = read_skill("ghost", str(tmp_path))
    assert "not found" in result


def test_read_skill_invalid_name(tmp_path):
    result = read_skill("../evil", str(tmp_path))
    assert result.startswith("Error")


def test_read_skill_missing_skill_md(tmp_path):
    (tmp_path / "broken").mkdir()
    result = read_skill("broken", str(tmp_path))
    assert "missing skill.md" in result


def test_read_skill_md_only(tmp_path):
    (tmp_path / "simple").mkdir()
    (tmp_path / "simple" / "skill.md").write_text("Follow these steps.\n")
    result = read_skill("simple", str(tmp_path))
    assert "Follow these steps." in result


def test_read_skill_does_not_include_py(tmp_path):
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "skill.md").write_text("Instructions.\n")
    (tmp_path / "full" / "skill.py").write_text(_VALID_PY)
    result = read_skill("full", str(tmp_path))
    assert "Instructions." in result
    assert "def read_file" not in result


# ── execute_skill ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_skill_invalid_name(tmp_path):
    registry = _mock_registry()
    result = await execute_skill("../evil", "target", str(tmp_path), registry)
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_execute_skill_not_found(tmp_path):
    registry = _mock_registry()
    result = await execute_skill("ghost", "target", str(tmp_path), registry)
    assert "not found" in result


@pytest.mark.asyncio
async def test_execute_skill_no_py_returns_error(tmp_path):
    (tmp_path / "simple").mkdir()
    (tmp_path / "simple" / "skill.md").write_text("Follow these steps.\n")
    registry = _mock_registry()
    result = await execute_skill("simple", "some-target", str(tmp_path), registry)
    assert "no skill.py" in result


@pytest.mark.asyncio
async def test_execute_skill_runs_target(tmp_path):
    skill_dir = tmp_path / "full"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("Instructions.\n")
    (skill_dir / "skill.py").write_text(_VALID_PY)

    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))

    # write a temp file to read
    test_file = tmp_path / "hello.txt"
    test_file.write_text("hello world")
    result = await execute_skill("full", "read_file", str(tmp_path), registry, kwargs={"path": str(test_file)})
    assert "hello world" in result


@pytest.mark.asyncio
async def test_execute_skill_missing_required_arg(tmp_path):
    skill_dir = tmp_path / "full"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("Instructions.\n")
    (skill_dir / "skill.py").write_text(_VALID_PY)

    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))

    result = await execute_skill("full", "read_file", str(tmp_path), registry, kwargs={})
    assert "missing required argument" in result
    assert "path" in result


@pytest.mark.asyncio
async def test_execute_skill_unknown_target(tmp_path):
    skill_dir = tmp_path / "full"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("Instructions.\n")
    (skill_dir / "skill.py").write_text(_VALID_PY)

    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))

    result = await execute_skill("full", "nonexistent", str(tmp_path), registry)
    assert "no target" in result


@pytest.mark.asyncio
async def test_execute_skill_rejected_skill(tmp_path):
    skill_dir = tmp_path / "evil"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("Instructions.\n")
    (skill_dir / "skill.py").write_text(_VALID_PY)

    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(False, "contains eval")),
    ):
        await registry.load_skills_dir(str(tmp_path))

    result = await execute_skill("evil", "read_file", str(tmp_path), registry)
    assert "not valid" in result


# ── create_skill ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_skill_invalid_name(tmp_path):
    registry = _mock_registry()
    result = await create_skill("../evil", "Evil skill.", "instructions", str(tmp_path), registry)
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_create_skill_md_only(tmp_path):
    registry = _mock_registry()
    result = await create_skill("myskill", "A test skill.", "Do this thing.", str(tmp_path), registry)
    assert result.startswith("Created skill 'myskill'")
    assert "(no tools)" in result
    written = (tmp_path / "myskill" / "skill.md").read_text()
    assert "Do this thing." in written
    assert not (tmp_path / "myskill" / "skill.py").exists()


@pytest.mark.asyncio
async def test_create_skill_auto_frontmatter(tmp_path):
    registry = _mock_registry()
    await create_skill("myskill", "A test skill.", "Do this thing.", str(tmp_path), registry)
    written = (tmp_path / "myskill" / "skill.md").read_text()
    assert written.startswith("---")
    assert 'description: "A test skill."' in written


@pytest.mark.asyncio
async def test_create_skill_preserves_existing_frontmatter(tmp_path):
    registry = _mock_registry()
    md = '---\ndescription: "Already there."\n---\n\nDo this.\n'
    await create_skill("myskill", "Ignored desc.", md, str(tmp_path), registry)
    written = (tmp_path / "myskill" / "skill.md").read_text()
    assert written.startswith("---")
    assert "Already there." in written


@pytest.mark.asyncio
async def test_create_skill_with_py(tmp_path):
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        result = await create_skill("full", "A full skill.", "Instructions.", str(tmp_path), registry, py_content=_VALID_PY)
    assert result.startswith("Created skill 'full'")
    assert "2 tool(s)" in result
    assert (tmp_path / "full" / "skill.py").exists()


@pytest.mark.asyncio
async def test_create_skill_rejected_py_removes_file(tmp_path):
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(False, "unsafe code")),
    ):
        result = await create_skill("bad", "Bad skill.", "Instructions.", str(tmp_path), registry, py_content=_VALID_PY)
    assert "Error" in result
    assert not (tmp_path / "bad" / "skill.py").exists()


# ── validate_skill ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_skill_invalid_name(tmp_path):
    registry = _mock_registry()
    result = await validate_skill("../evil", str(tmp_path), registry)
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_validate_skill_not_found(tmp_path):
    registry = _mock_registry()
    result = await validate_skill("ghost", str(tmp_path), registry)
    assert "not found" in result


@pytest.mark.asyncio
async def test_validate_skill_missing_md(tmp_path):
    (tmp_path / "broken").mkdir()
    registry = _mock_registry()
    result = await validate_skill("broken", str(tmp_path), registry)
    assert "missing skill.md" in result


@pytest.mark.asyncio
async def test_validate_skill_md_only(tmp_path):
    (tmp_path / "simple").mkdir()
    (tmp_path / "simple" / "skill.md").write_text("Instructions.\n")
    registry = _mock_registry()
    result = await validate_skill("simple", str(tmp_path), registry)
    assert result.startswith("OK")
    assert "no tools" in result


@pytest.mark.asyncio
async def test_validate_skill_ok_with_py(tmp_path):
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "skill.md").write_text("Instructions.\n")
    (tmp_path / "full" / "skill.py").write_text(_VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        result = await validate_skill("full", str(tmp_path), registry)
    assert result.startswith("OK")
    assert "2 tool(s)" in result


@pytest.mark.asyncio
async def test_validate_skill_reports_invalid(tmp_path):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "skill.md").write_text("Instructions.\n")
    (tmp_path / "bad" / "skill.py").write_text("def broken(\n")
    registry = SkillRegistry(model="test-model")
    result = await validate_skill("bad", str(tmp_path), registry)
    assert "INVALID" in result


# ── BUILTIN_SCHEMAS ───────────────────────────────────────────────────────────


def test_builtin_schemas_has_five_entries():
    assert len(BUILTIN_SCHEMAS) == 5


def test_builtin_schemas_names():
    names = {s["function"]["name"] for s in BUILTIN_SCHEMAS}
    assert names == {"list_skills", "read_skill", "execute_skill", "create_skill", "validate_skill"}


def test_builtin_schemas_are_function_type():
    for schema in BUILTIN_SCHEMAS:
        assert schema["type"] == "function"


def test_builtin_schemas_required_params():
    by_name = {s["function"]["name"]: s["function"] for s in BUILTIN_SCHEMAS}
    assert by_name["list_skills"]["parameters"]["required"] == []
    assert by_name["read_skill"]["parameters"]["required"] == ["name"]
    assert by_name["execute_skill"]["parameters"]["required"] == ["name", "target"]
    assert set(by_name["create_skill"]["parameters"]["required"]) == {"name", "description", "md_content"}
    assert by_name["validate_skill"]["parameters"]["required"] == ["name"]


def test_execute_skill_schema_has_kwargs_not_params():
    by_name = {s["function"]["name"]: s["function"] for s in BUILTIN_SCHEMAS}
    props = by_name["execute_skill"]["parameters"]["properties"]
    assert "kwargs" in props
    assert "params" not in props


def test_create_skill_schema_has_py_content_not_mk_content():
    by_name = {s["function"]["name"]: s["function"] for s in BUILTIN_SCHEMAS}
    props = by_name["create_skill"]["parameters"]["properties"]
    assert "py_content" in props
    assert "mk_content" not in props


# ── get_builtin_tools ─────────────────────────────────────────────────────────


def test_get_builtin_tools_returns_all_five(tmp_path):
    registry = _mock_registry()
    tools = get_builtin_tools(str(tmp_path), registry=registry)
    assert set(tools.keys()) == {"list_skills", "read_skill", "execute_skill", "create_skill", "validate_skill"}


def test_get_builtin_tools_list_skills_callable(tmp_path):
    registry = _mock_registry()
    tools = get_builtin_tools(str(tmp_path), registry=registry)
    result = tools["list_skills"]()
    assert "No skills found" in result


@pytest.mark.asyncio
async def test_get_builtin_tools_validate_skill_callable(tmp_path):
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "skill.md").write_text("Instructions.\n")
    (tmp_path / "ok" / "skill.py").write_text(_VALID_PY)
    registry = SkillRegistry(model="test-model")
    tools = get_builtin_tools(str(tmp_path), registry=registry)
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        result = await tools["validate_skill"](name="ok")
    assert result.startswith("OK")


@pytest.mark.asyncio
async def test_get_builtin_tools_execute_skill_no_py_returns_error(tmp_path):
    (tmp_path / "simple").mkdir()
    (tmp_path / "simple" / "skill.md").write_text("Instructions.\n")
    registry = _mock_registry()
    tools = get_builtin_tools(str(tmp_path), registry=registry)
    result = await tools["execute_skill"](name="simple", target="some-target")
    assert "no skill.py" in result
