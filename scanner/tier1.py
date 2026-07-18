"""Tier 1 — Pattern matching scanner (regex, file checks, no LLM)."""

from __future__ import annotations

import os
import re
from typing import Any

from config import CompiledPattern
from models.context import ProjectContext
from models.finding import Finding, Severity
from models.fix import Fix
from utils.files import get_file_extension, read_file_safe
from utils.git import get_gitignore_entries, has_gitignore, is_file_tracked, is_git_repo
from utils.logger import get_logger

_log = get_logger("tier1")

_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
}

# Scanner rule/pattern metadata — not application code; matching here causes self-scan noise.
_RULE_DEFINITION_SUFFIXES = (
    "/config/patterns.yaml",
    "/config/rules.yaml",
)


def scan_tier1(
    context: ProjectContext,
    patterns: dict[str, list[CompiledPattern]],
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Run all Tier 1 checks against the project.

    Args:
        context: Project context from discovery.
        patterns: Compiled regex patterns grouped by category.
        rules: Rule definitions keyed by rule_id.

    Returns:
        Deduplicated list of findings sorted by severity.
    """
    findings: list[Finding] = []

    _log.info("Running Tier 1 scan on %d files", len(context.file_manifest))

    for file_info in context.file_manifest:
        file_findings = _scan_file_patterns(file_info.path, patterns, rules)
        findings.extend(file_findings)

    findings.extend(_check_env_files(context, rules))
    findings.extend(_check_gitignore(context, rules))

    findings = _deduplicate(findings)
    findings.sort(key=lambda f: (
        0 if f.severity == Severity.CRITICAL else 1 if f.severity == Severity.WARNING else 2,
        f.file_path,
        f.line_start or 0,
    ))

    _log.info("Tier 1 found %d issues", len(findings))
    return findings


def _is_rule_definition_file(file_path: str) -> bool:
    """Return True when a file holds scanner rule metadata, not app source code."""
    normalized = file_path.replace("\\", "/")
    return any(normalized.endswith(suffix) for suffix in _RULE_DEFINITION_SUFFIXES)


def _scan_file_patterns(
    file_path: str,
    patterns: dict[str, list[CompiledPattern]],
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Run all applicable regex patterns against a single file.

    Args:
        file_path: Absolute path to the file.
        patterns: Compiled patterns grouped by category.
        rules: Rule definitions.

    Returns:
        List of findings from pattern matches.
    """
    if _is_rule_definition_file(file_path):
        return []

    content = read_file_safe(file_path)
    if content is None:
        return []

    ext = get_file_extension(file_path)
    lines = content.splitlines()
    findings: list[Finding] = []

    for category, pattern_list in patterns.items():
        for pattern in pattern_list:
            if not _extension_matches(ext, pattern.file_extensions):
                continue

            for line_num, line in enumerate(lines, start=1):
                if _is_comment_line(line, ext):
                    continue

                match = pattern.regex.search(line)
                if not match:
                    continue

                if pattern.exclude_patterns:
                    if any(ep.search(line) for ep in pattern.exclude_patterns):
                        continue

                rule = rules.get(pattern.rule_id, {})
                severity = _SEVERITY_MAP.get(rule.get("severity", "warning"), Severity.WARNING)

                fix = _suggest_fix(pattern, line, file_path)

                findings.append(Finding(
                    rule_id=pattern.rule_id,
                    severity=severity,
                    category=rule.get("category", category),
                    title=rule.get("title", pattern.name),
                    description=rule.get("description", f"Pattern '{pattern.name}' matched."),
                    file_path=file_path,
                    tier=1,
                    line_start=line_num,
                    line_end=line_num,
                    code_snippet=line.strip(),
                    fix=fix,
                ))

    return findings


def _check_env_files(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check if .env files are tracked by git.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings for tracked .env files.
    """
    findings: list[Finding] = []

    if not is_git_repo(context.project_path):
        return findings

    for env_path in context.env_files:
        basename = os.path.basename(env_path)
        if basename == ".env.example":
            continue

        if is_file_tracked(context.project_path, env_path):
            rule = rules.get("SEC-002", {})
            findings.append(Finding(
                rule_id="SEC-002",
                severity=Severity.CRITICAL,
                category="secrets",
                title=rule.get("title", "Exposed .env file"),
                description=f"{basename} is tracked by git and may contain secrets.",
                file_path=env_path,
                tier=1,
                fix=Fix(
                    description=f"Remove {basename} from git tracking and add it to .gitignore.",
                    code=f"git rm --cached {basename}\necho '{basename}' >> .gitignore",
                    file_path=".gitignore",
                    fix_type="insert",
                ),
            ))

    return findings


def _check_gitignore(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check if .gitignore is missing entries for .env files.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings for missing .gitignore entries.
    """
    findings: list[Finding] = []

    if not has_gitignore(context.project_path):
        if context.env_files:
            rule = rules.get("SEC-002", {})
            findings.append(Finding(
                rule_id="SEC-002",
                severity=Severity.WARNING,
                category="secrets",
                title="Missing .gitignore",
                description="No .gitignore file found. Environment files may be committed.",
                file_path=os.path.join(context.project_path, ".gitignore"),
                tier=1,
                fix=Fix(
                    description="Create a .gitignore with .env entries.",
                    code=".env\n.env.local\n.env.production\n.env.development",
                    file_path=".gitignore",
                    fix_type="create_file",
                ),
            ))
        return findings

    entries = get_gitignore_entries(context.project_path)
    env_patterns = {".env", ".env.local", ".env.production", ".env.development", ".env.*"}
    has_env_ignore = any(
        entry in env_patterns or entry.startswith(".env")
        for entry in entries
    )

    if not has_env_ignore and context.env_files:
        rule = rules.get("SEC-002", {})
        findings.append(Finding(
            rule_id="SEC-002",
            severity=Severity.WARNING,
            category="secrets",
            title="Missing .env in .gitignore",
            description=".gitignore exists but does not include .env file patterns.",
            file_path=os.path.join(context.project_path, ".gitignore"),
            tier=1,
            fix=Fix(
                description="Add .env to .gitignore.",
                code=".env\n.env.*",
                file_path=".gitignore",
                fix_type="insert",
            ),
        ))

    return findings


def _extension_matches(file_ext: str, allowed: list[str]) -> bool:
    """Check if a file extension matches the pattern's allowed list.

    Args:
        file_ext: File extension (e.g., ".py").
        allowed: Allowed extensions, or ["*"] for all.

    Returns:
        True if the file should be scanned with this pattern.
    """
    if "*" in allowed:
        return True
    return file_ext in allowed


def _is_comment_line(line: str, ext: str) -> bool:
    """Check if a line is a comment (simple heuristic).

    Args:
        line: Source code line.
        ext: File extension.

    Returns:
        True if the line appears to be a comment.
    """
    stripped = line.strip()
    if ext in {".py"}:
        return stripped.startswith("#")
    if ext in {".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"}:
        return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")
    return False


def _suggest_fix(pattern: CompiledPattern, line: str, file_path: str) -> Fix | None:
    """Generate a fix suggestion based on the pattern type.

    Args:
        pattern: The matched pattern.
        line: The matched source line.
        file_path: Path to the file.

    Returns:
        A Fix suggestion, or None.
    """
    name = pattern.name

    if name in {"hardcoded_password", "hardcoded_token", "generic_secret_assignment"}:
        return Fix(
            description="Move this value to an environment variable.",
            code='os.environ.get("SECRET_NAME")  # or process.env.SECRET_NAME',
            file_path=file_path,
            fix_type="replace",
        )

    if name.endswith("_key") or "api_key" in name or "secret" in name:
        return Fix(
            description="Move this API key to an environment variable and load it at runtime.",
            code='os.environ["API_KEY"]  # or process.env.API_KEY',
            file_path=file_path,
            fix_type="replace",
        )

    if name == "connection_string":
        return Fix(
            description="Move the connection string to an environment variable.",
            code='os.environ["DATABASE_URL"]  # or process.env.DATABASE_URL',
            file_path=file_path,
            fix_type="replace",
        )

    if name in {"eval_usage", "exec_usage_python"}:
        return Fix(
            description="Avoid eval/exec. Use safer alternatives like JSON.parse() or ast.literal_eval().",
            code="# Use ast.literal_eval() for Python or JSON.parse() for JavaScript",
            file_path=file_path,
            fix_type="replace",
        )

    if name == "innerhtml_assignment":
        return Fix(
            description="Use textContent or a sanitization library instead of innerHTML.",
            code="element.textContent = userInput; // or use DOMPurify.sanitize()",
            file_path=file_path,
            fix_type="replace",
        )

    if name.startswith("sql_"):
        return Fix(
            description="Use parameterized queries instead of string concatenation.",
            code="cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            file_path=file_path,
            fix_type="replace",
        )

    if name.startswith("cors"):
        return Fix(
            description="Restrict CORS to specific trusted origins.",
            code='cors({ origin: "https://yourdomain.com" })',
            file_path=file_path,
            fix_type="replace",
        )

    if name.startswith("default_"):
        return Fix(
            description="Remove default credentials and use strong, unique values.",
            code="# Use environment variables for credentials",
            file_path=file_path,
            fix_type="replace",
        )

    if name.startswith("console_log") or name.startswith("print_sensitive"):
        return Fix(
            description="Remove or redact sensitive data from log output.",
            code="# Remove this log statement or redact sensitive values",
            file_path=file_path,
            fix_type="replace",
        )

    return None


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings (same file, same line, same rule).

    Args:
        findings: Raw list of findings.

    Returns:
        Deduplicated findings, keeping the one with more detail.
    """
    seen: dict[tuple[str, int | None, str], Finding] = {}

    for f in findings:
        key = (f.file_path, f.line_start, f.rule_id)
        existing = seen.get(key)
        if existing is None:
            seen[key] = f
        elif len(f.description) > len(existing.description):
            seen[key] = f

    return list(seen.values())
