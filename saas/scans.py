"""Scan service — runs the core scanner on uploaded projects and persists results."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass

from sqlalchemy.orm import Session

from orchestrator import ScanOptions, run
from saas.config import get_plan, load_settings
from saas.database import Scan, User
from utils.archive import ArchiveError, archive_root, safe_extract_zip
from utils.github import GitHubError, fetch_repo
from utils.logger import get_logger

_log = get_logger("saas.scans")


@dataclass
class ScanResult:
    """The outcome of a scan.

    Args:
        scan_id: The persisted scan record ID.
        report_json: The full JSON report.
        summary: The summary dict (totals by severity).
    """

    scan_id: int
    report_json: dict
    summary: dict


class ScanError(Exception):
    """Raised when a scan cannot be completed."""


def _persist_scan(
    session: Session,
    user: User,
    report_str: str,
    project_name: str,
) -> ScanResult:
    """Parse a report string and persist a Scan record.

    Args:
        session: Database session.
        user: The requesting user.
        report_str: JSON report from the orchestrator.
        project_name: Display name for the scan.

    Returns:
        A populated ScanResult.

    Raises:
        ScanError: If the report is invalid JSON.
    """
    try:
        report = json.loads(report_str)
    except json.JSONDecodeError as exc:
        raise ScanError("Scanner produced an invalid report.") from exc

    summary = report.get("summary", {})
    scan_info = report.get("scan_info", {})

    scan = Scan(
        user_id=user.id,
        project_name=project_name,
        framework=scan_info.get("framework", "unknown"),
        total_findings=int(summary.get("total", 0)),
        critical_findings=int(summary.get("critical", 0)),
        warning_findings=int(summary.get("warning", 0)),
        tiers_run=scan_info.get("tiers_run", "1, 2"),
        report_json=report_str,
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    return ScanResult(scan_id=scan.id, report_json=report, summary=summary)


def _check_tier3_allowed(user: User, skip_tier3: bool) -> None:
    """Raise ScanError if the user's plan disallows Tier 3.

    Args:
        user: The requesting user.
        skip_tier3: Whether Tier 3 is skipped.

    Raises:
        ScanError: If Tier 3 is requested but not allowed on the plan.
    """
    plan = get_plan(user.plan)
    if not skip_tier3 and not plan.tier3_enabled:
        raise ScanError(
            f"Tier 3 (deep AI analysis) is not available on the {plan.name} plan. "
            f"Upgrade to Pro to enable it."
        )


def run_scan_from_archive(
    session: Session,
    user: User,
    archive_path: str,
    project_name: str,
    skip_tier3: bool = True,
) -> ScanResult:
    """Extract an uploaded archive, scan it, and persist the results.

    Args:
        session: Database session.
        user: The requesting user.
        archive_path: Path to the uploaded zip archive.
        project_name: Display name for the scan.
        skip_tier3: Whether to skip LLM analysis.

    Returns:
        A populated ScanResult.

    Raises:
        ScanError: If the scan fails or the plan disallows Tier 3.
    """
    _check_tier3_allowed(user, skip_tier3)

    with tempfile.TemporaryDirectory(prefix="vibesafe_scan_") as work_dir:
        try:
            safe_extract_zip(archive_path, work_dir)
        except ArchiveError as exc:
            raise ScanError(str(exc)) from exc
        scan_root = archive_root(work_dir)

        _log.info("Running SaaS scan for user %s on %s", user.id, project_name)
        report_str = run(
            scan_root,
            ScanOptions(output_format="json", skip_tier3=skip_tier3),
        )

    return _persist_scan(session, user, report_str, project_name)


def run_scan_from_github(
    session: Session,
    user: User,
    repo: str,
    project_name: str,
    skip_tier3: bool = True,
    token: str | None = None,
) -> ScanResult:
    """Fetch a GitHub repository, scan it, and persist the results.

    Args:
        session: Database session.
        user: The requesting user.
        repo: Repository slug or URL.
        project_name: Display name for the scan.
        skip_tier3: Whether to skip LLM analysis.
        token: Optional GitHub token (falls back to server GITHUB_TOKEN).

    Returns:
        A populated ScanResult.

    Raises:
        ScanError: If the scan fails or the plan disallows Tier 3.
    """
    _check_tier3_allowed(user, skip_tier3)

    settings = load_settings()
    gh_token = token or settings.github_token
    max_bytes = settings.max_upload_mb * 1024 * 1024

    try:
        with fetch_repo(repo, token=gh_token, max_download_bytes=max_bytes) as scan_root:
            _log.info("Running SaaS GitHub scan for user %s on %s", user.id, repo)
            report_str = run(
                scan_root,
                ScanOptions(output_format="json", skip_tier3=skip_tier3),
            )
    except GitHubError as exc:
        raise ScanError(str(exc)) from exc

    return _persist_scan(session, user, report_str, project_name)
