"""File explorer skill tools."""

from __future__ import annotations

import fnmatch
import os
import re

from mapache_agent import target


@target
def list_files(dir: str) -> str:
    """List files and directories in the specified directory.

    :param dir: Directory to list contents of
    """
    import subprocess

    result = subprocess.run(["ls", "-la", dir], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ls failed for {dir!r}")
    return result.stdout


@target
def search_by_name(name: str, dir: str) -> str:
    """Search for files by name pattern in a directory recursively.

    :param name: Filename or pattern to search for (supports wildcards)
    :param dir: Directory to search in
    """
    matches = []
    for root, _dirs, files in os.walk(dir):
        for fname in files:
            if fnmatch.fnmatch(fname, name):
                matches.append(os.path.join(root, fname))
    return "\n".join(matches) if matches else "No matches found"


@target
def search_by_extension(ext: str, dir: str) -> str:
    """Search for files by extension in a directory recursively.

    :param ext: File extension to search for (without dot, e.g. txt or py)
    :param dir: Directory to search in
    """
    matches = []
    for root, _dirs, files in os.walk(dir):
        for fname in files:
            if fname.endswith(f".{ext}"):
                matches.append(os.path.join(root, fname))
    return "\n".join(matches) if matches else "No matches found"


@target
def grep_in_files(pattern: str, dir: str) -> str:
    """Search for a text pattern in files within a directory recursively.

    :param pattern: Pattern to search for (regex supported)
    :param dir: Directory to search in
    """
    compiled = re.compile(pattern)
    results = []
    for root, _dirs, files in os.walk(dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if compiled.search(line):
                            results.append(f"{fpath}:{lineno}: {line.rstrip()}")
            except OSError:
                pass
    return "\n".join(results) if results else "No matches found"
