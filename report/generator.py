"""Report assembly — deduplication, sorting, summary stats."""

from __future__ import annotations

from typing import Any

from models.finding import Finding, Severity
from utils.logger import get_logger

_log = get_logger("report")


def generate_report(
    findings: list[Finding],
    context_info: dict[str, Any],
    output_format: str = "markdown",
) -> str:
    """Generate a formatted report from all findings.

    Args:
        findings: Combined findings from all tiers.
        context_info: Scan metadata (framework, files_scanned, scan_time, etc.).
        output_format: Output format — "markdown" or "json".

    Returns:
        Formatted report string.
    """
    from report.formatter import format_json, format_markdown

    deduped = deduplicate(findings)
    sorted_findings = sort_findings(deduped)
    summary = compute_summary(sorted_findings)

    _log.info(
        "Report: %d findings (%d critical, %d warning, %d info)",
        summary["total"], summary["critical"], summary["warning"], summary["info"],
    )

    if output_format == "json":
        return format_json(sorted_findings, summary, context_info)

    return format_markdown(sorted_findings, summary, context_info)


def deduplicate(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings, keeping the richer version.

    Args:
        findings: Raw list of findings from all tiers.

    Returns:
        Deduplicated findings.
    """
    seen: dict[tuple[str, int | None, str], Finding] = {}

    for f in findings:
        key = (f.file_path, f.line_start, f.rule_id)
        existing = seen.get(key)

        if existing is None:
            seen[key] = f
        else:
            if _richness(f) > _richness(existing):
                seen[key] = f

    return list(seen.values())


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity (critical first), then category, then file path.

    Args:
        findings: List of findings.

    Returns:
        Sorted list.
    """
    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return sorted(findings, key=lambda f: (
        severity_order.get(f.severity, 3),
        f.category,
        f.file_path,
        f.line_start or 0,
    ))


def compute_summary(findings: list[Finding]) -> dict[str, Any]:
    """Compute summary statistics for the report.

    Args:
        findings: Sorted, deduplicated findings.

    Returns:
        Summary dict with counts and metadata.
    """
    critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    warning = sum(1 for f in findings if f.severity == Severity.WARNING)
    info = sum(1 for f in findings if f.severity == Severity.INFO)

    categories = set(f.category for f in findings)
    files_with_issues = set(f.file_path for f in findings)

    return {
        "total": len(findings),
        "critical": critical,
        "warning": warning,
        "info": info,
        "categories": sorted(categories),
        "files_with_issues": len(files_with_issues),
    }


def _richness(finding: Finding) -> int:
    """Score how detailed a finding is (for deduplication tie-breaking).

    Args:
        finding: A finding to score.

    Returns:
        Richness score (higher = more detail).
    """
    score = len(finding.description)
    if finding.fix:
        score += 50
    if finding.code_snippet:
        score += 20
    if finding.tier == 3:
        score += 30
    return score
