"""Tests for SkillRegistry: hash detection, import, re-validation trigger."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mapache_agent.skill_registry import SkillEntry, SkillRegistry, _sha256, _syntax_check


# ── helpers ───────────────────────────────────────────────────────────────────

_VALID_PY = """\
from mapache_agent import target

@target
def greet(name: str) -> str:
    \"\"\"Greet someone.

    :param name: The name to greet
    \"\"\"
    return f"Hello, {name}"
"""

_SYNTAX_ERROR_PY = "def broken(\n"


def _make_skill(tmp_path: Path, name: str, py_content: str) -> Path:
    """Write skill.md + skill.py under tmp_path/name and return the skill dir."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(f'---\ndescription: "{name}"\n---\n')
    py_path = skill_dir / "skill.py"
    py_path.write_text(py_content, encoding="utf-8")
    return skill_dir


# ── _sha256 ───────────────────────────────────────────────────────────────────


def test_sha256_returns_hex_string(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"hello")
    digest = _sha256(f)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_sha256_changes_on_content_change(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"hello")
    h1 = _sha256(f)
    f.write_bytes(b"world")
    h2 = _sha256(f)
    assert h1 != h2


# ── _syntax_check ─────────────────────────────────────────────────────────────


def test_syntax_check_valid(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("x = 1\n")
    assert _syntax_check(f) is None


def test_syntax_check_invalid(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(_SYNTAX_ERROR_PY)
    err = _syntax_check(f)
    assert err is not None
    assert "SyntaxError" in err or "syntax" in err.lower() or "EOF" in err


# ── SkillRegistry.load_skills_dir ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_skills_dir_imports_valid_skill(tmp_path):
    _make_skill(tmp_path, "greeter", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))
    entry = registry.get_cached_entry("greeter")
    assert entry is not None
    assert entry.valid is True
    assert "greet" in entry.tools


@pytest.mark.asyncio
async def test_load_skills_dir_rejects_syntax_error(tmp_path):
    _make_skill(tmp_path, "broken", _SYNTAX_ERROR_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))
    entry = registry.get_cached_entry("broken")
    assert entry is not None
    assert entry.valid is False
    assert "Syntax error" in (entry.reject_reason or "")


@pytest.mark.asyncio
async def test_load_skills_dir_rejects_unsafe(tmp_path):
    _make_skill(tmp_path, "evil", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(False, "contains eval")),
    ):
        await registry.load_skills_dir(str(tmp_path))
    entry = registry.get_cached_entry("evil")
    assert entry is not None
    assert entry.valid is False
    assert "eval" in (entry.reject_reason or "")


@pytest.mark.asyncio
async def test_load_skills_dir_skips_dir_without_skill_md(tmp_path):
    skill_dir = tmp_path / "no-md"
    skill_dir.mkdir()
    (skill_dir / "skill.py").write_text(_VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))
    assert registry.get_cached_entry("no-md") is None


@pytest.mark.asyncio
async def test_load_skills_dir_missing_dir(tmp_path):
    registry = SkillRegistry(model="test-model")
    # Should not raise
    await registry.load_skills_dir(str(tmp_path / "nonexistent"))


# ── SkillRegistry.get_entry (hash-change re-validation) ──────────────────────


@pytest.mark.asyncio
async def test_get_entry_returns_cached_when_unchanged(tmp_path):
    _make_skill(tmp_path, "stable", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ) as mock_check:
        await registry.load_skills_dir(str(tmp_path))
        call_count_after_load = mock_check.call_count
        # Call get_entry without changing the file
        entry = await registry.get_entry("stable")
        # LLM should NOT be called again
        assert mock_check.call_count == call_count_after_load
    assert entry is not None
    assert entry.valid is True


@pytest.mark.asyncio
async def test_get_entry_revalidates_on_hash_change(tmp_path):
    skill_dir = _make_skill(tmp_path, "mutable", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))

    # Modify the file
    (skill_dir / "skill.py").write_text(_VALID_PY + "\n# changed\n")

    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ) as mock_check:
        entry = await registry.get_entry("mutable")
        assert mock_check.call_count == 1  # re-validated

    assert entry is not None
    assert entry.valid is True


@pytest.mark.asyncio
async def test_get_entry_returns_none_for_unknown_skill(tmp_path):
    registry = SkillRegistry(model="test-model")
    entry = await registry.get_entry("ghost")
    assert entry is None


# ── SkillRegistry.load_or_add ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_or_add_adds_new_skill(tmp_path):
    _make_skill(tmp_path, "fresh", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        entry = await registry.load_or_add("fresh", str(tmp_path))
    assert entry is not None
    assert entry.valid is True
    assert "greet" in entry.tools


@pytest.mark.asyncio
async def test_load_or_add_returns_none_when_no_skill_py(tmp_path):
    skill_dir = tmp_path / "md-only"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("instructions\n")
    registry = SkillRegistry(model="test-model")
    entry = await registry.load_or_add("md-only", str(tmp_path))
    assert entry is None


# ── tool function is callable ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_imported_tool_is_callable(tmp_path):
    _make_skill(tmp_path, "callable-skill", _VALID_PY)
    registry = SkillRegistry(model="test-model")
    with patch(
        "mapache_agent.skill_registry._llm_security_check",
        new=AsyncMock(return_value=(True, None)),
    ):
        await registry.load_skills_dir(str(tmp_path))
    entry = registry.get_cached_entry("callable-skill")
    assert entry is not None
    fn = entry.tools["greet"].fn
    assert fn(name="World") == "Hello, World"
