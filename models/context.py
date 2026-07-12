"""Project context data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileInfo:
    """Metadata about a single file in the project.

    Args:
        path: Absolute path to the file.
        file_type: File extension (e.g., ".py", ".js").
        size_bytes: File size in bytes.
        relevance_score: Security relevance score from 0.0 to 1.0.
    """

    path: str
    file_type: str
    size_bytes: int
    relevance_score: float = 0.0


@dataclass
class ProjectContext:
    """Complete context about a scanned project.

    Args:
        project_path: Root directory of the project.
        framework: Detected framework (e.g., "nextjs", "express", "generic").
        language: Primary language (e.g., "javascript", "python").
        file_manifest: All relevant files with metadata.
        entry_points: Main server/app entry files.
        config_files: Framework and project config files.
        env_files: Environment variable files (.env, .env.local, etc.).
        package_manager: Detected package manager ("npm", "pip", etc.) or None.
    """

    project_path: str
    framework: str
    language: str
    file_manifest: list[FileInfo] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    package_manager: Optional[str] = None
