"""Centralised path helpers for ~/.mapache-agent project directories.

All app-related files live under a hidden directory in the user's home folder::

    ~/.mapache-agent/<project-slug>/agents/      # default agents directory
    ~/.mapache-agent/<project-slug>/logs/        # log files

The *project slug* is derived from the absolute working directory by stripping
the leading ``/`` and replacing every remaining ``/`` with ``_``.

Example:  ``/Users/alice/proj/myapp``  →  ``Users_alice_proj_myapp``
"""

from __future__ import annotations

import os
from pathlib import Path

_APP_HOME = Path.home() / ".mapache-agent"


def project_slug(cwd: str | None = None) -> str:
    """Return the project slug for *cwd* (defaults to ``os.getcwd()``)."""
    path = cwd or os.getcwd()
    return path.lstrip("/").replace("/", "_")


def project_dir(cwd: str | None = None) -> Path:
    """Return ``~/.mapache-agent/<slug>/``, creating it if necessary."""
    directory = _APP_HOME / project_slug(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_agents_dir(cwd: str | None = None) -> str:
    """Return ``~/.mapache-agent/<slug>/agents/`` as a string, creating it if necessary."""
    directory = project_dir(cwd) / "agents"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


def default_skills_dir(cwd: str | None = None) -> str:
    """Return ``~/.mapache-agent/<slug>/skills/`` as a string, creating it if necessary."""
    directory = project_dir(cwd) / "skills"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


def log_file(cwd: str | None = None) -> str:
    """Return ``~/.mapache-agent/<slug>/logs/mapache-agent.log`` as a string, creating the logs dir if necessary."""
    logs_dir = project_dir(cwd) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return str(logs_dir / "mapache-agent.log")


def settings_file(cwd: str | None = None) -> Path:
    """Return ``~/.mapache-agent/<slug>/settings.yaml`` as a Path (does not create the file)."""
    return project_dir(cwd) / "settings.yaml"
