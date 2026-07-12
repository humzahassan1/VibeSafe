"""Tools the agent can invoke during the investigation loop."""

from __future__ import annotations

import re
from dataclasses import dataclass

from utils.files import get_file_extension, read_file_safe, walk_project
from utils.logger import get_logger

_log = get_logger("tools")

_IMPORT_PATTERNS = {
    ".py": [
        re.compile(r'^import\s+([\w.]+)', re.MULTILINE),
        re.compile(r'^from\s+([\w.]+)\s+import', re.MULTILINE),
    ],
    ".js": [
        re.compile(r'import\s+.*?from\s+["\']([^"\']+)["\']', re.MULTILINE),
        re.compile(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', re.MULTILINE),
    ],
    ".ts": [
        re.compile(r'import\s+.*?from\s+["\']([^"\']+)["\']', re.MULTILINE),
        re.compile(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', re.MULTILINE),
    ],
}
_IMPORT_PATTERNS[".jsx"] = _IMPORT_PATTERNS[".js"]
_IMPORT_PATTERNS[".tsx"] = _IMPORT_PATTERNS[".ts"]


@dataclass
class SearchMatch:
    """A single pattern search match.

    Args:
        file_path: Path to the file.
        line_number: Line number of the match.
        line_text: The matched line text.
    """

    file_path: str
    line_number: int
    line_text: str


def read_file(path: str) -> str | None:
    """Read a file and log the access.

    Args:
        path: Absolute path to the file.

    Returns:
        File contents, or None on error.
    """
    _log.debug("Agent reading: %s", path)
    return read_file_safe(path)


def list_directory(path: str) -> list[str]:
    """List files in a directory, respecting ignore rules.

    Args:
        path: Directory to list.

    Returns:
        List of absolute file paths.
    """
    _log.debug("Agent listing: %s", path)
    return walk_project(path)


def search_pattern(pattern: str, paths: list[str]) -> list[SearchMatch]:
    """Search for a regex pattern across multiple files.

    Args:
        pattern: Regex pattern string.
        paths: List of file paths to search.

    Returns:
        List of SearchMatch results.
    """
    _log.debug("Agent searching pattern: %s across %d files", pattern, len(paths))
    matches: list[SearchMatch] = []

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        _log.warning("Invalid search pattern '%s': %s", pattern, e)
        return matches

    for path in paths:
        content = read_file_safe(path)
        if content is None:
            continue

        for i, line in enumerate(content.splitlines(), start=1):
            if compiled.search(line):
                matches.append(SearchMatch(
                    file_path=path,
                    line_number=i,
                    line_text=line.strip(),
                ))

    return matches


def get_imports(path: str) -> list[str]:
    """Extract import/require statements from a file.

    Args:
        path: Path to the source file.

    Returns:
        List of imported module names.
    """
    _log.debug("Agent extracting imports: %s", path)
    content = read_file_safe(path)
    if content is None:
        return []

    ext = get_file_extension(path)
    patterns = _IMPORT_PATTERNS.get(ext, [])

    imports: list[str] = []
    for pat in patterns:
        imports.extend(pat.findall(content))

    return imports
