# AGENTS.md

Guidance for AI coding assistants working on this repository.

## What this project does

**mapache-agent** is a Python AI agent framework extended by *skills*. A skill is a subdirectory containing a `skill.md` (Markdown instructions for the LLM) and an optional `skill.py` (Python functions decorated with `@target` that become LLM-callable tools). The system prompt is read from `SYSTEM.md` in the working directory or project data dir.

## Repository layout

```
mapache_agent/          # Source package
  main.py            # CLI entry point (argparse, settings resolution)
  agent.py           # Agent class — conversation loop, LLM calls
  agent_shell.py     # Interactive REPL (cmd.Cmd wrapper)
  skill.py           # @target decorator and skill module loader/validator
  skill_registry.py  # Skill discovery and in-process registry
  commands.py        # Interactive shell commands (/help, /export, /stats)
  builtin_tools/     # Built-in tools always injected into every agent
    __init__.py
    skill_tools.py   # list/read/execute/create/validate skill tools
    memory_tools.py  # FTS5 search and recall over past messages
  memory.py          # SQLite + FTS5 persistent memory
  settings.py        # Per-project settings (~/.mapache-agent/<slug>/settings.yaml)
  app_dirs.py        # Path helpers (~/.mapache-agent/)
  templates/         # Bundled SYSTEM.md template
examples/            # Example skills (file-edit, file-explorer)
tests/               # Pytest test suite
```

## Development commands

```bash
uv run pytest                  # Run all tests (195 collected)
uv run pytest --e2e            # Include end-to-end tests (call real LLM API)
uv run ruff check mapache_agent/  # Lint
uv run ruff format mapache_agent/ # Format
```

All tests live in `tests/`. End-to-end tests are marked `@pytest.mark.e2e` and skipped by default.

## Key conventions

- **Python 3.11+** required.
- Dependency management via `uv`. The lockfile is `uv.lock`; update it with `uv lock` after changing `pyproject.toml`.
- The project uses `any-llm-sdk` (not litellm) for LLM access.
- One CLI entry point: `mapache_agent` (run agent).
- Per-project data lives in `~/.mapache-agent/<project-slug>/` — never write to the repo at runtime.
- Ruff is the linter and formatter. Rule `E741` (ambiguous variable names) is ignored.
- Always run `uv run pytest` and `uv run ruff check mapache_agent/` before finishing a change.
