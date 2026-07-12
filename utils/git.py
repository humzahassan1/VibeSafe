"""Git-aware helpers for checking repository state."""

from __future__ import annotations

import os
import subprocess

from utils.logger import get_logger

_log = get_logger("git")


def is_git_repo(path: str) -> bool:
    """Check if a directory is inside a git repository.

    Args:
        path: Directory path to check.

    Returns:
        True if the directory contains a .git folder or is inside a git repo.
    """
    return os.path.isdir(os.path.join(path, ".git"))


def has_gitignore(path: str) -> bool:
    """Check if a .gitignore file exists in the project root.

    Args:
        path: Project root directory.

    Returns:
        True if .gitignore exists.
    """
    return os.path.isfile(os.path.join(path, ".gitignore"))


def get_gitignore_entries(path: str) -> list[str]:
    """Parse .gitignore and return the list of patterns.

    Args:
        path: Project root directory containing .gitignore.

    Returns:
        List of gitignore patterns, empty list if no .gitignore.
    """
    gitignore_path = os.path.join(path, ".gitignore")
    if not os.path.isfile(gitignore_path):
        return []

    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        _log.warning("Could not read .gitignore: %s", e)
        return []

    entries = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.append(stripped)
    return entries


def is_file_tracked(repo_path: str, file_path: str) -> bool:
    """Check if a file is tracked by git.

    Args:
        repo_path: Root of the git repository.
        file_path: Path to the file to check.

    Returns:
        True if the file is tracked by git. False if untracked or not a git repo.
    """
    if not is_git_repo(repo_path):
        return False

    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("Git check failed for %s: %s", file_path, e)
        return False
