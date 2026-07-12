"""Finding and Severity data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from models.fix import Fix


class Severity(Enum):
    """Severity levels for security findings."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    """A single security finding from any detection tier.

    Args:
        rule_id: Rule identifier (e.g., SEC-001).
        severity: Finding severity level.
        category: Rule category (e.g., "secrets", "auth").
        title: Short description of the finding.
        description: Detailed explanation of the risk.
        file_path: Path to the file containing the issue.
        tier: Detection tier that produced this finding (1, 2, or 3).
        line_start: Starting line number of the issue.
        line_end: Ending line number of the issue.
        code_snippet: The problematic code.
        fix: Suggested fix for the issue.
        confidence: Confidence score (0.0 to 1.0), mainly for Tier 3.
    """

    rule_id: str
    severity: Severity
    category: str
    title: str
    description: str
    file_path: str
    tier: int
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    code_snippet: Optional[str] = None
    fix: Optional[Fix] = None
    confidence: float = 1.0
