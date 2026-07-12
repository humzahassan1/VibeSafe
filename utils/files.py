"""Safe, consistent file I/O used by every module."""

from __future__ import annotations

import os
from pathlib import Path

from utils.logger import get_logger

_log = get_logger("files")

DEFAULT_IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "dist", "build",
    "venv", ".venv", "coverage", ".cache", ".tox", ".mypy_cache",
    ".pytest_cache", "egg-info",
}

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".o", ".obj",
    ".pyc", ".pyo", ".class", ".jar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}


def read_file_safe(path: str) -> str | None:
    """Read a text file safely, returning None on any error.

    Args:
        path: Absolute path to the file.

    Returns:
        File contents as string, or None if the file cannot be read.
    """
    try:
        if is_binary(path):
            _log.warning("Skipping binary file: %s", path)
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except PermissionError:
        _log.warning("Permission denied: %s", path)
        return None
    except FileNotFoundError:
        _log.warning("File not found: %s", path)
        return None
    except OSError as e:
        _log.warning("Could not read file %s: %s", path, e)
        return None


def walk_project(
    path: str,
    ignore_dirs: set[str] | None = None,
) -> list[str]:
    """Recursively walk a project directory, skipping ignored directories and binaries.

    Args:
        path: Root directory to walk.
        ignore_dirs: Directory names to skip. Uses DEFAULT_IGNORE_DIRS if None.

    Returns:
        List of absolute paths to relevant files.
    """
    if ignore_dirs is None:
        ignore_dirs = DEFAULT_IGNORE_DIRS

    results: list[str] = []
    root_path = os.path.realpath(path)
    seen_dirs: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        real_dir = os.path.realpath(dirpath)
        if real_dir in seen_dirs:
            dirnames.clear()
            continue
        seen_dirs.add(real_dir)

        dirnames[:] = [
            d for d in dirnames
            if d not in ignore_dirs and not d.endswith(".egg-info")
        ]

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            ext = get_file_extension(filename)
            if ext not in _BINARY_EXTENSIONS:
                results.append(os.path.abspath(file_path))

    return results


def is_binary(path: str) -> bool:
    """Check if a file is binary by inspecting the first 8192 bytes.

    Args:
        path: Path to the file.

    Returns:
        True if the file appears to be binary.
    """
    ext = get_file_extension(path)
    if ext in _BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        return True


def get_file_extension(path: str) -> str:
    """Get the lowercase file extension.

    Args:
        path: File path or name.

    Returns:
        Extension including the dot (e.g., ".py"), or empty string.
    """
    return Path(path).suffix.lower()


def get_file_size(path: str) -> int:
    """Get file size in bytes.

    Args:
        path: Path to the file.

    Returns:
        File size in bytes, or 0 on error.
    """
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
