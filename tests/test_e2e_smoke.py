"""Smoke e2e tests — run the real CLI against the live API.

Skip by default; opt in with:  pytest --e2e -m e2e
"""

import subprocess
import sys

import pytest

MODEL = "anthropic/claude-haiku-4-5"


def _run(prompt: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "mapache_agent.main", "run", "--model", MODEL, "--prompt", prompt]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.e2e
def test_list_available_tools():
    result = _run("What tools are available to you? Just list their names.")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "Expected non-empty output"
    assert "list_skills" in result.stdout, "Expected 'list_skills' tool to be available"


@pytest.mark.e2e
def test_list_available_skills():
    result = _run("List available skills.", extra_args=["--skills-dir", "examples"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "Expected non-empty output"
