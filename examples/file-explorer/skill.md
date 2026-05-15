---
description: "Navigate and search the filesystem by name, extension, or content"
---

# File Explorer Skill

This skill provides tools to navigate directories and search the local filesystem by filename, extension, or text content.

## Usage

Start with `list_files` to orient yourself in a directory. Use `search_by_name` or `search_by_extension` to locate files, and `grep_in_files` to find files containing a specific pattern.

## Available tools

Call `execute_skill(name="file-explorer", target="<function>", kwargs={...})`.

- `list_files(dir)` — List files and directories in the specified directory
- `search_by_name(name, dir)` — Search for files by name pattern recursively (supports wildcards)
- `search_by_extension(ext, dir)` — Search for files by extension recursively (e.g., `ext="py"`)
- `grep_in_files(pattern, dir)` — Search for a text pattern in files recursively
