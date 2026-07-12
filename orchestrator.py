"""Pipeline runner — the only file that knows about all modules."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from config import Config, load_config
from models.context import ProjectContext
from models.finding import Finding
from report.generator import generate_report
from scanner.discovery import discover
from scanner.tier1 import scan_tier1
from scanner.tier2 import scan_tier2
from scanner.tier3 import scan_tier3
from utils.logger import get_logger

_log = get_logger("orchestrator")


@dataclass
class ScanOptions:
    """Options for a scan run.

    Args:
        output_format: Report format — "markdown" or "json".
        skip_tier3: If True, skip LLM-based analysis.
        token_budget: Max token budget for Tier 3.
        model: LLM model override.
    """

    output_format: str = "markdown"
    skip_tier3: bool = False
    token_budget: int = 100_000
    model: str | None = None


def run(project_path: str, options: ScanOptions | None = None) -> str:
    """Execute the full scan pipeline and return a formatted report.

    Args:
        project_path: Path to the project to scan.
        options: Scan configuration options.

    Returns:
        Formatted report string.
    """
    if options is None:
        options = ScanOptions()

    start_time = time.time()

    _log.info("Loading configuration...")
    config = load_config()

    _log.info("Phase 1: Discovery...")
    try:
        context = discover(project_path, config.frameworks)
    except FileNotFoundError as e:
        raise SystemExit(str(e))

    if not context.file_manifest:
        return _empty_report(context, options, time.time() - start_time)

    _log.info("Phase 2: Tier 1 scan (pattern matching)...")
    tier1_findings = _run_tier1(context, config)

    _log.info("Phase 3: Tier 2 scan (config analysis)...")
    tier2_findings = _run_tier2(context, config)

    tier3_findings: list[Finding] = []
    if not options.skip_tier3:
        _log.info("Phase 4: Tier 3 scan (LLM analysis)...")
        tier3_findings = _run_tier3(
            context, tier1_findings, tier2_findings, config, options
        )
    else:
        _log.info("Phase 4: Skipped (--skip-tier3)")

    all_findings = tier1_findings + tier2_findings + tier3_findings

    elapsed = time.time() - start_time
    _log.info("Phase 5: Generating report...")

    context_info = {
        "framework": context.framework,
        "language": context.language,
        "files_scanned": len(context.file_manifest),
        "scan_time": f"{elapsed:.1f}s",
        "project_path": context.project_path,
        "tiers_run": "1, 2" if options.skip_tier3 else "1, 2, 3",
    }

    report = generate_report(all_findings, context_info, options.output_format)

    _log.info("Scan complete in %.1fs — %d findings", elapsed, len(all_findings))
    return report


def run_github(
    repo: str,
    options: ScanOptions | None = None,
    token: str | None = None,
    ref: str | None = None,
) -> str:
    """Fetch a GitHub repository and run the scan pipeline on it.

    Args:
        repo: Repository slug or URL (``owner/repo``, ``owner/repo@ref``, or github.com URL).
        options: Scan configuration options.
        token: Optional GitHub token (falls back to ``GITHUB_TOKEN`` env).
        ref: Optional branch/tag/commit override (applied after parsing ``repo``).

    Returns:
        Formatted report string.

    Raises:
        SystemExit: If the repository cannot be fetched.
    """
    from utils.github import GitHubError, RepoRef, fetch_repo, parse_repo_ref

    if options is None:
        options = ScanOptions()

    if token is None:
        import os
        token = os.environ.get("GITHUB_TOKEN")

    parsed = parse_repo_ref(repo)
    if ref:
        parsed = RepoRef(parsed.owner, parsed.repo, ref)

    slug = f"{parsed.owner}/{parsed.repo}"
    if parsed.ref:
        slug = f"{slug}@{parsed.ref}"

    try:
        with fetch_repo(slug, token=token) as local_path:
            return run(local_path, options)
    except GitHubError as exc:
        raise SystemExit(str(exc)) from exc


def _run_tier1(context: ProjectContext, config: Config) -> list[Finding]:
    """Run Tier 1 scan with error handling.

    Args:
        context: Project context.
        config: Loaded configuration.

    Returns:
        Tier 1 findings, or empty list on failure.
    """
    try:
        return scan_tier1(context, config.patterns, config.rules)
    except Exception as e:
        _log.error("Tier 1 scan failed: %s", e)
        return []


def _run_tier2(context: ProjectContext, config: Config) -> list[Finding]:
    """Run Tier 2 scan with error handling.

    Args:
        context: Project context.
        config: Loaded configuration.

    Returns:
        Tier 2 findings, or empty list on failure.
    """
    try:
        return scan_tier2(context, config.rules)
    except Exception as e:
        _log.error("Tier 2 scan failed: %s", e)
        return []


def _run_tier3(
    context: ProjectContext,
    tier1_findings: list[Finding],
    tier2_findings: list[Finding],
    config: Config,
    options: ScanOptions,
) -> list[Finding]:
    """Run Tier 3 scan with error handling.

    Args:
        context: Project context.
        tier1_findings: Tier 1 findings.
        tier2_findings: Tier 2 findings.
        config: Loaded configuration.
        options: Scan options.

    Returns:
        Tier 3 findings, or empty list on failure.
    """
    try:
        return scan_tier3(
            context,
            tier1_findings,
            tier2_findings,
            config.rules,
            token_budget=options.token_budget,
            model=options.model,
        )
    except Exception as e:
        _log.error("Tier 3 scan failed: %s — returning Tier 1/2 results only", e)
        return []


def _empty_report(context: ProjectContext, options: ScanOptions, elapsed: float) -> str:
    """Generate a report for a project with no scannable files.

    Args:
        context: Project context.
        options: Scan options.
        elapsed: Time elapsed.

    Returns:
        Empty report string.
    """
    context_info = {
        "framework": context.framework,
        "language": context.language,
        "files_scanned": 0,
        "scan_time": f"{elapsed:.1f}s",
        "project_path": context.project_path,
        "tiers_run": "none",
    }
    return generate_report([], context_info, options.output_format)
