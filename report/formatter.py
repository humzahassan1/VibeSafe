"""Output formatting — markdown and JSON."""

from __future__ import annotations

import json
import os
from typing import Any

from jinja2 import Environment, FileSystemLoader

from models.finding import Finding, Severity
from utils.logger import get_logger

_log = get_logger("formatter")

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def format_markdown(
    findings: list[Finding],
    summary: dict[str, Any],
    context_info: dict[str, Any],
) -> str:
    """Render findings as a markdown report.

    Args:
        findings: Sorted, deduplicated findings.
        summary: Summary statistics.
        context_info: Scan metadata.

    Returns:
        Markdown report string.
    """
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    info = [f for f in findings if f.severity == Severity.INFO]

    template = _jinja_env.get_template("report.md.jinja")
    return template.render(
        summary=summary,
        context=context_info,
        critical=critical,
        warnings=warnings,
        info=info,
        findings=findings,
    )


def format_json(
    findings: list[Finding],
    summary: dict[str, Any],
    context_info: dict[str, Any],
) -> str:
    """Render findings as a JSON report.

    Args:
        findings: Sorted, deduplicated findings.
        summary: Summary statistics.
        context_info: Scan metadata.

    Returns:
        JSON report string.
    """
    data = {
        "summary": summary,
        "scan_info": context_info,
        "findings": [_finding_to_dict(f) for f in findings],
    }
    return json.dumps(data, indent=2, default=str)


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Convert a Finding to a JSON-serializable dict.

    Args:
        finding: Finding instance.

    Returns:
        Dict representation.
    """
    d: dict[str, Any] = {
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "category": finding.category,
        "title": finding.title,
        "description": finding.description,
        "file_path": finding.file_path,
        "tier": finding.tier,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "code_snippet": finding.code_snippet,
        "confidence": finding.confidence,
    }

    if finding.fix:
        d["fix"] = {
            "description": finding.fix.description,
            "code": finding.fix.code,
            "file_path": finding.fix.file_path,
            "fix_type": finding.fix.fix_type,
        }

    return d
