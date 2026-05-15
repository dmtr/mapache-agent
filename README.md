# mapache-agent

An AI agent powered by Python skills.

Skills extend the agent with domain-specific instructions (`skill.md`) and optional Python tool functions (`skill.py`). Each function decorated with `@target` becomes callable by the agent. The system prompt is read from `SYSTEM.md`.

## Installation

```
pip install mapache-agent
```

Requires Python 3.11+. Uses [any-llm-sdk](https://pypi.org/project/any-llm-sdk/) for model access — set the appropriate API key (e.g. `ANTHROPIC_API_KEY`) in the environment.

## Usage

```
ANTHROPIC_API_KEY=<key> mapache_agent [run] [--model MODEL] [--prompt PROMPT | --prompt-file FILE] [--with-memory]
```

- `--model MODEL` — any-llm model string. Defaults to the value in `settings.yaml`.
- `--system PROMPT` — system prompt string (overrides `SYSTEM.md` discovery)
- `--system-file FILE` — read system prompt from file (overrides `SYSTEM.md` discovery)
- `--prompt PROMPT` — send a single prompt and exit instead of entering the interactive shell
- `--prompt-file FILE` — send a single prompt read from `FILE` and exit
- `--skills-dir DIR` — directory for skill subdirectories (default: `~/.mapache-agent/<project>/skills/`)
- `--with-memory` — enable persistent conversation memory (see [Memory](#memory))
- `--disable-builtin-tools TOOLS` — comma-separated built-in tool names to disable, or `all`
- `--max-tool-output CHARS` — truncate tool output to this many characters; `0` = unlimited (default: 16000)
- `--max-tokens N` — max tokens in the model response (default: 4096)
- `--reasoning-effort EFFORT` — reasoning effort level: `none|minimal|low|medium|high|xhigh|auto` (default: `auto`)
- `--max-retries N` — max retry attempts on rate limit errors (default: 5)
- `--tool-timeout SECONDS` — timeout for each tool call (default: 600)
- `--loglevel LEVEL` — set logging level to DEBUG, INFO, WARNING, ERROR, or CRITICAL (default: INFO)

Without `--prompt`, the agent starts an interactive REPL. Use `/exit` or `/quit` (or press Ctrl-D) to leave.

Interactive shell commands:

- `/help` — show available shell commands
- `/export` — export the current conversation to `conversation-<timestamp>.html`
- `/stats` — show token usage totals for this session (when memory is enabled)

## Project settings

All per-project data is stored under `~/.mapache-agent/`:

```
~/.mapache-agent/
└── <project-slug>/          # e.g. Users_alice_proj_myapp
    ├── settings.yaml        # default model
    ├── memory.db            # conversation history (when memory is enabled)
    ├── skills/              # skill subdirectories
    └── logs/
        └── mapache-agent.log   # log output at the selected --loglevel
```

The **project slug** is the absolute path of the working directory with the leading `/` stripped and remaining `/` replaced by `_`.

### settings.yaml

```yaml
model: anthropic/claude-haiku-4-5-20251001
memory: true          # optional — enable persistent memory
reasoning_effort: low # optional — none|minimal|low|medium|high|xhigh|auto
```

All fields are optional. CLI flags always take precedence over `settings.yaml` values.

## Skills

A skill is a subdirectory inside the skills directory containing:

- **`skill.md`** (required) — instructions the agent reads before acting; includes a YAML front-matter `description` field shown by `list_skills`
- **`skill.py`** (optional) — Python module with `@target`-decorated tool functions

### skill.md

```markdown
---
description: "One-line description shown in list_skills."
---

# My Skill

Instructions for the agent on how and when to use this skill.

## Available tools

Call `execute_skill(name="my-skill", target="do_thing", kwargs={"param": "value"})`.

- `do_thing(param: str)` — does a thing with param
```

### skill.py

```python
from mapache_agent import target

@target
def do_thing(param: str) -> str:
    """Does a thing.

    :param param: The input parameter
    """
    return f"did: {param}"
```

Rules for `skill.py`:
- Decorate every tool function with `@target`.
- Annotate parameters with Python type hints (`str`, `int`, `float`, `bool`).
- Document parameters with `:param name: description` in the docstring.
- Functions must be synchronous.
- Run `validate_skill` after creating a skill — it performs an LLM security check.

## Built-in tools

Every agent automatically receives these built-in tools:

| Tool | What it does |
|---|---|
| `list_skills` | List available skills; shows `[has tools]` for skills with a `skill.py` |
| `read_skill(name)` | Load a skill's `skill.md` instructions |
| `execute_skill(name, target, kwargs)` | Call a `@target` function in a skill's `skill.py` |
| `create_skill(name, description, md_content, py_content)` | Create or overwrite a skill |
| `validate_skill(name)` | LLM security-check a skill's `skill.py` |

You can disable specific built-ins with `--disable-builtin-tools list_skills,validate_skill` (or `all`).

### execute_skill

```python
execute_skill(
    name="file-edit",      # skill directory name
    target="read_file",    # @target function name
    kwargs={"file": "README.md"}
)
```

### Security

When a skill with a `skill.py` is first loaded, the agent:

1. Computes a SHA-256 hash of the file.
2. Runs a syntax check (`py_compile`).
3. Calls the LLM to inspect the code for malicious patterns.
4. Imports the module only if the LLM returns `SAFE`.

On subsequent runs the hash is compared — if it has changed, the skill is re-validated before use.

## Memory

Agents can persist every conversation turn to a local SQLite database and search it in future sessions.

### Enabling memory

```bash
# One-time flag
mapache_agent --with-memory

# Always on for this project (settings.yaml)
memory: true
```

The database is stored at `~/.mapache-agent/<project-slug>/memory.db`.

### Memory tools

When memory is enabled, three additional built-in tools are injected:

| Tool | What it does |
|---|---|
| `get_recent_messages(limit, from_date, to_date)` | Return recent messages in chronological order |
| `search_user_memory(query, limit, from_date, to_date)` | FTS5 keyword search over past user messages |
| `search_agent_memory(query, limit, from_date, to_date)` | FTS5 keyword search over past agent replies |

**FTS5 search tips** — the search is keyword-based, not semantic:

- Use short keywords: `"goal project"` not `"what is the goal of this project"`
- Use `OR` for broader recall: `"goal OR objective OR purpose"`
- Stop words (`the`, `of`, `is`, `a`) are not indexed — omit them
- Use `get_recent_messages` when you need recent context and don't know which keywords to search

## Examples

Two example skills are included in `examples/`:

### file-edit

```bash
mapache_agent --skills-dir examples --model anthropic/claude-haiku-4-5-20251001
```

| Target | Description |
|---|---|
| `list_files(dir)` | List files and directories at a path |
| `read_file(file)` | Read the full contents of a file |
| `read_lines(file, start, end)` | Read a line range (1-based) |
| `write_file(file, content)` | Create or overwrite a file |
| `append_to_file(file, content)` | Append content to a file |
| `replace_in_file(file, old, new)` | Replace first occurrence of a string in a file |

### file-explorer

| Target | Description |
|---|---|
| `list_files(dir)` | List contents of a directory |
| `search_by_name(name, dir)` | Find files by name pattern (wildcards supported) |
| `search_by_extension(ext, dir)` | Find files by extension |
| `grep_in_files(pattern, dir)` | Search for a regex pattern across files |

## Running tests

```
uv run pytest
```
