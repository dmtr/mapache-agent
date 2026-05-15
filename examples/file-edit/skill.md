---
description: "Read, write, and edit text files on the filesystem"
---

# File Edit Skill

This skill provides tools to read, write, and precisely modify text files on the local filesystem.

## Usage

Before editing, read the file first to understand its current content. Use `replace_in_file` for targeted changes and `write_file` only when rewriting the whole file. Always verify results by reading the file again after making changes.

## Available tools

Call `execute_skill(name="file-edit", target="<function>", kwargs={...})`.

- `list_files(dir=".")` — List files and directories at the given path
- `count_lines(file)` — Count the total number of lines in a file
- `read_file(file)` — Read and return the full contents of a file
- `read_lines(file, start, end=0)` — Read a specific line range (1-based; `end=0` means end of file)
- `write_file(file, content)` — Create or overwrite a file with the given content
- `append_to_file(file, content)` — Append content to the end of a file
- `replace_in_file(file, old, new)` — Replace the first occurrence of a literal string in a file
