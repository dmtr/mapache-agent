"""File editing skill tools."""

from __future__ import annotations

import os

from mapache_agent import target


@target
def list_files(dir: str = ".") -> str:
    """List files and directories at the given path.

    :param dir: Directory to list (use . for the current directory)
    """
    import subprocess

    result = subprocess.run(["ls", "-la", dir], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ls failed for {dir!r}")
    return result.stdout


@target
def count_lines(file: str) -> str:
    """Count the total number of lines in a file.

    :param file: Path to the file
    """
    if not os.path.isfile(file):
        raise FileNotFoundError(f"file not found: {file}")
    with open(file, encoding="utf-8", errors="replace") as f:
        count = sum(1 for _ in f)
    return str(count)


@target
def read_file(file: str) -> str:
    """Read and return the full contents of a file.

    :param file: Path to the file
    """
    if not os.path.isfile(file):
        raise FileNotFoundError(f"file not found: {file}")
    return open(file, encoding="utf-8", errors="replace").read()


@target
def read_lines(file: str, start: int, end: int = 0) -> str:
    """Read a range of lines from a file (1-based line numbers).

    If end is 0, reads from start to the last line of the file.

    :param file: Path to the file
    :param start: First line to read (1-based)
    :param end: Last line to read inclusive; 0 means end of file
    """
    if not os.path.isfile(file):
        raise FileNotFoundError(f"file not found: {file}")
    with open(file, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    stop = len(lines) if end == 0 else end
    return "".join(lines[start - 1 : stop])


@target
def write_file(file: str, content: str) -> str:
    """Create or overwrite a file with the given content.

    Creates parent directories automatically if they do not exist.

    :param file: Path of the file to write
    :param content: Text content to write (may be multiline)
    """
    os.makedirs(os.path.dirname(os.path.abspath(file)), exist_ok=True)
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written: {file}"


@target
def append_to_file(file: str, content: str) -> str:
    """Append content to the end of a file.

    :param file: Path to the file
    :param content: Content to append
    """
    with open(file, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended to: {file}"


@target
def replace_in_file(file: str, old: str, new: str) -> str:
    """Replace the first occurrence of a literal string in a file.

    :param file: Path to the file
    :param old: The string to find (exact match)
    :param new: The replacement string
    """
    if not os.path.isfile(file):
        raise FileNotFoundError(f"file not found: {file}")
    text = open(file, encoding="utf-8").read()
    if old not in text:
        raise ValueError(f"string not found in {file!r}")
    updated = text.replace(old, new, 1)
    with open(file, "w", encoding="utf-8") as f:
        f.write(updated)
    return f"Replaced in: {file}"
