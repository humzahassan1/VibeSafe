"""Project structure scanning, stack detection, and file relevance scoring."""

from __future__ import annotations

import fnmatch
import json
import os
from typing import Any

from models.context import FileInfo, ProjectContext
from utils.files import get_file_extension, get_file_size, walk_project, read_file_safe
from utils.logger import get_logger

_log = get_logger("discovery")

_ENTRY_POINT_NAMES = {
    "app.js", "app.ts", "server.js", "server.ts", "index.js", "index.ts",
    "main.py", "app.py", "manage.py", "wsgi.py",
}

_ENV_PATTERNS = {".env", ".env.local", ".env.production", ".env.development", ".env.test"}

_HIGH_RELEVANCE_DIRS = {"routes", "api", "middleware", "auth", "controllers", "models", "db"}

_HIGH_RELEVANCE_NAMES = {
    "auth", "login", "signup", "register", "session", "middleware",
    "password", "permissions", "roles", "admin", "payment", "checkout",
    "stripe", "webhook", "supabase", "firebase",
}

_LOW_RELEVANCE_DIRS = {"test", "tests", "__tests__", "docs", "documentation", "scripts", "public", "static"}


def discover(project_path: str, frameworks_config: dict[str, Any]) -> ProjectContext:
    """Scan a project directory and build a complete ProjectContext.

    Args:
        project_path: Root directory of the project to scan.
        frameworks_config: Framework detection signatures from config.

    Returns:
        Fully populated ProjectContext.
    """
    abs_path = os.path.abspath(project_path)
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(
            f"Project path '{project_path}' does not exist. "
            f"Run vibesafe scan with a valid directory path."
        )

    _log.info("Scanning project: %s", abs_path)

    file_paths = walk_project(abs_path)
    framework, language = detect_framework(abs_path, file_paths, frameworks_config)

    _log.info("Detected framework: %s (%s)", framework, language)

    fw_config = frameworks_config.get(framework, frameworks_config.get("generic", {}))
    high_risk_patterns = fw_config.get("high_risk_patterns", [])

    manifest: list[FileInfo] = []
    entry_points: list[str] = []
    config_files: list[str] = []
    env_files: list[str] = []

    for fp in file_paths:
        basename = os.path.basename(fp)
        ext = get_file_extension(fp)
        size = get_file_size(fp)
        rel_path = os.path.relpath(fp, abs_path)

        score = score_relevance(rel_path, basename, ext, high_risk_patterns)

        manifest.append(FileInfo(
            path=fp,
            file_type=ext,
            size_bytes=size,
            relevance_score=score,
        ))

        if basename in _ENTRY_POINT_NAMES:
            entry_points.append(fp)

        if basename in _ENV_PATTERNS or basename.startswith(".env"):
            env_files.append(fp)

        fw_configs = fw_config.get("config_files", [])
        if basename in fw_configs or rel_path in fw_configs:
            config_files.append(fp)

    manifest.sort(key=lambda f: f.relevance_score, reverse=True)

    package_manager = _detect_package_manager(abs_path)

    _log.info("Found %d files (%d high-relevance)", len(manifest),
              sum(1 for f in manifest if f.relevance_score >= 0.7))

    return ProjectContext(
        project_path=abs_path,
        framework=framework,
        language=language,
        file_manifest=manifest,
        entry_points=entry_points,
        config_files=config_files,
        env_files=env_files,
        package_manager=package_manager,
    )


def detect_framework(
    project_path: str,
    file_paths: list[str],
    frameworks_config: dict[str, Any],
) -> tuple[str, str]:
    """Detect the project's framework and language.

    Args:
        project_path: Root directory.
        file_paths: All discovered file paths.
        frameworks_config: Framework detection signatures.

    Returns:
        Tuple of (framework_name, language).
    """
    basenames = {os.path.basename(fp) for fp in file_paths}
    rel_dirs = set()
    for fp in file_paths:
        rel = os.path.relpath(os.path.dirname(fp), project_path)
        parts = rel.split(os.sep)
        for p in parts:
            rel_dirs.add(p)

    package_deps = _get_package_dependencies(project_path)

    for fw_name, fw_cfg in frameworks_config.items():
        if fw_name == "generic":
            continue

        for marker in fw_cfg.get("file_markers", []):
            if marker in basenames:
                _log.debug("Framework %s detected via file marker: %s", fw_name, marker)
                return fw_name, fw_cfg.get("language", "unknown")

        for dep in fw_cfg.get("package_dependencies", []):
            if dep in package_deps:
                _log.debug("Framework %s detected via dependency: %s", fw_name, dep)
                return fw_name, fw_cfg.get("language", "unknown")

    language = _guess_language(file_paths)
    return "generic", language


def score_relevance(
    rel_path: str,
    basename: str,
    ext: str,
    high_risk_patterns: list[str],
) -> float:
    """Assign a security relevance score to a file.

    Args:
        rel_path: Path relative to project root.
        basename: File name.
        ext: File extension.
        high_risk_patterns: Glob patterns for high-risk files from framework config.

    Returns:
        Score from 0.0 to 1.0.
    """
    score = 0.3

    path_parts = rel_path.replace("\\", "/").lower().split("/")
    name_lower = basename.lower().replace(ext, "")

    for part in path_parts:
        if part in _HIGH_RELEVANCE_DIRS:
            score = max(score, 0.8)
            break

    for keyword in _HIGH_RELEVANCE_NAMES:
        if keyword in name_lower:
            score = max(score, 0.8)
            break

    for pattern in high_risk_patterns:
        if fnmatch.fnmatch(rel_path.replace("\\", "/"), pattern):
            score = max(score, 0.9)
            break

    if basename in _ENV_PATTERNS or basename.startswith(".env"):
        score = max(score, 0.9)

    if basename in _ENTRY_POINT_NAMES:
        score = max(score, 0.7)

    if ext in {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".conf"}:
        if any(kw in name_lower for kw in ("config", "setting", "firebase", "supabase")):
            score = max(score, 0.8)

    for part in path_parts:
        if part in _LOW_RELEVANCE_DIRS:
            score = min(score, 0.2)
            break

    return min(score, 1.0)


def _get_package_dependencies(project_path: str) -> set[str]:
    """Extract dependency names from package.json or requirements.txt.

    Args:
        project_path: Project root.

    Returns:
        Set of dependency names.
    """
    deps: set[str] = set()

    pkg_json = os.path.join(project_path, "package.json")
    if os.path.isfile(pkg_json):
        content = read_file_safe(pkg_json)
        if content:
            try:
                data = json.loads(content)
                for key in ("dependencies", "devDependencies"):
                    if key in data and isinstance(data[key], dict):
                        deps.update(data[key].keys())
            except (json.JSONDecodeError, TypeError):
                _log.warning("Could not parse package.json at %s", pkg_json)

    req_txt = os.path.join(project_path, "requirements.txt")
    if os.path.isfile(req_txt):
        content = read_file_safe(req_txt)
        if content:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
                    deps.add(name.lower())

    return deps


def _detect_package_manager(project_path: str) -> str | None:
    """Detect the package manager used by the project.

    Args:
        project_path: Project root.

    Returns:
        Package manager name or None.
    """
    if os.path.isfile(os.path.join(project_path, "package-lock.json")):
        return "npm"
    if os.path.isfile(os.path.join(project_path, "yarn.lock")):
        return "yarn"
    if os.path.isfile(os.path.join(project_path, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.isfile(os.path.join(project_path, "bun.lockb")):
        return "bun"
    if os.path.isfile(os.path.join(project_path, "requirements.txt")):
        return "pip"
    if os.path.isfile(os.path.join(project_path, "Pipfile")):
        return "pipenv"
    if os.path.isfile(os.path.join(project_path, "poetry.lock")):
        return "poetry"
    if os.path.isfile(os.path.join(project_path, "package.json")):
        return "npm"
    return None


def _guess_language(file_paths: list[str]) -> str:
    """Guess the primary language from file extensions.

    Args:
        file_paths: All files found in the project.

    Returns:
        Best-guess language name.
    """
    ext_counts: dict[str, int] = {}
    for fp in file_paths:
        ext = get_file_extension(fp)
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    lang_map = {
        ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".mjs": "javascript", ".cjs": "javascript",
        ".py": "python", ".rb": "ruby", ".php": "php",
        ".go": "go", ".rs": "rust", ".java": "java",
    }

    best_lang = "unknown"
    best_count = 0
    for ext, count in ext_counts.items():
        if ext in lang_map and count > best_count:
            best_count = count
            best_lang = lang_map[ext]

    return best_lang
