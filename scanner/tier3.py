"""Tier 3 — LLM-powered deep security analysis."""

from __future__ import annotations

import os
from typing import Any

from agent.loop import run_agent
from models.context import FileInfo, ProjectContext
from models.finding import Finding, Severity
from utils.logger import get_logger

_log = get_logger("tier3")

DEFAULT_TOKEN_BUDGET = 100_000

_ANALYSIS_CATEGORIES = {
    "auth": {
        "templates": ["auth_analysis.txt"],
        "keywords": ["auth", "login", "session", "middleware", "permission", "role", "jwt", "token"],
        "route_patterns": True,
    },
    "injection": {
        "templates": ["injection_analysis.txt"],
        "keywords": ["query", "sql", "db", "database", "input", "form", "upload", "request"],
        "route_patterns": True,
    },
    "data_flow": {
        "templates": ["data_flow.txt"],
        "keywords": ["route", "api", "handler", "controller", "endpoint", "webhook", "payment"],
        "route_patterns": True,
    },
    "ai_security": {
        "templates": ["ai_security.txt"],
        "keywords": ["ai", "llm", "openai", "anthropic", "gpt", "claude", "prompt", "completion", "chat"],
        "route_patterns": False,
    },
    "scalability": {
        "templates": ["scalability.txt"],
        "keywords": ["server", "app", "handler", "worker", "queue", "async"],
        "route_patterns": False,
    },
}


def scan_tier3(
    context: ProjectContext,
    tier1_findings: list[Finding],
    tier2_findings: list[Finding],
    rules: dict[str, dict[str, Any]],
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    model: str | None = None,
) -> list[Finding]:
    """Run all Tier 3 LLM analysis on the project.

    Args:
        context: Project context from discovery.
        tier1_findings: Findings from Tier 1.
        tier2_findings: Findings from Tier 2.
        rules: Rule definitions.
        token_budget: Maximum token budget for all Tier 3 analysis.
        model: LLM model override.

    Returns:
        List of findings from deep analysis.
    """
    all_prior = tier1_findings + tier2_findings
    selected = select_files_for_analysis(context, tier1_findings, tier2_findings)

    if not selected:
        _log.info("Tier 3: no files selected for analysis")
        return []

    _log.info("Tier 3: %d files selected for deep analysis", len(selected))

    all_findings: list[Finding] = []
    budget_per_category = token_budget // max(len(_ANALYSIS_CATEGORIES), 1)

    for cat_name, cat_config in _ANALYSIS_CATEGORIES.items():
        relevant_files = _filter_files_for_category(selected, cat_config, context)
        if not relevant_files:
            _log.debug("Skipping %s analysis — no relevant files", cat_name)
            continue

        file_paths = [fi.path for fi in relevant_files]
        _log.info("Running %s analysis on %d files", cat_name, len(file_paths))

        try:
            findings = run_agent(
                file_paths=file_paths,
                templates=cat_config["templates"],
                framework=context.framework,
                language=context.language,
                prior_findings=all_prior + all_findings,
                token_budget=budget_per_category,
                model=model,
            )
            all_findings.extend(findings)
        except Exception as e:
            _log.error("Tier 3 %s analysis failed: %s", cat_name, e)

    _log.info("Tier 3 found %d issues total", len(all_findings))
    return all_findings


def select_files_for_analysis(
    context: ProjectContext,
    tier1_findings: list[Finding],
    tier2_findings: list[Finding],
) -> list[FileInfo]:
    """Select which files to send to the LLM for deep analysis.

    Args:
        context: Project context.
        tier1_findings: Tier 1 findings.
        tier2_findings: Tier 2 findings.

    Returns:
        Prioritized list of files for Tier 3 analysis.
    """
    flagged_paths = set()
    for f in tier1_findings + tier2_findings:
        if f.severity in (Severity.CRITICAL, Severity.WARNING):
            flagged_paths.add(f.file_path)

    selected: list[FileInfo] = []
    seen: set[str] = set()

    for fi in context.file_manifest:
        if fi.path in seen:
            continue

        basename = os.path.basename(fi.path).lower()
        if any(basename.startswith(p) for p in ("test", "spec", "__test")):
            continue
        if any(basename.endswith(p) for p in (".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.py")):
            continue

        rel = os.path.relpath(fi.path, context.project_path).lower()
        if any(d in rel.split(os.sep) for d in ("test", "tests", "__tests__", "docs", "documentation")):
            continue

        is_flagged = fi.path in flagged_paths
        is_high_risk = fi.relevance_score >= 0.7

        if is_flagged or is_high_risk:
            selected.append(fi)
            seen.add(fi.path)

    selected.sort(key=lambda f: (
        0 if f.path in flagged_paths else 1,
        -f.relevance_score,
    ))

    return selected


def _filter_files_for_category(
    files: list[FileInfo],
    category_config: dict[str, Any],
    context: ProjectContext,
) -> list[FileInfo]:
    """Filter files relevant to a specific analysis category.

    Args:
        files: All selected files.
        category_config: Category configuration with keywords and patterns.
        context: Project context.

    Returns:
        Files relevant to this analysis category.
    """
    keywords = category_config.get("keywords", [])
    include_routes = category_config.get("route_patterns", False)

    relevant: list[FileInfo] = []
    for fi in files:
        basename = os.path.basename(fi.path).lower()
        rel_path = os.path.relpath(fi.path, context.project_path).lower()

        if any(kw in basename or kw in rel_path for kw in keywords):
            relevant.append(fi)
            continue

        if include_routes and fi.relevance_score >= 0.7:
            relevant.append(fi)
            continue

    return relevant
