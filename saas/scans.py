"""Scan service — runs the core scanner on uploaded projects and persists results."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass

from sqlalchemy.orm import Session

from orchestrator import ScanOptions, run
from saas.config import get_plan
from saas.database import Scan, User
from utils.logger import get_logger

_log = get_logger("saas.scans")

# Reject archives that expand to more than this many files (zip-bomb guard).
_MAX_FILES = 5000
# Reject any single extracted file larger than this.
_MAX_FILE_BYTES = 5 * 1024 * 1024


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


def _safe_extract(archive_path: str, dest_dir: str) -> None:
    """Extract a zip archive, guarding against path traversal and zip bombs.

    Args:
        archive_path: Path to the uploaded zip file.
        dest_dir: Directory to extract into.

    Raises:
        ScanError: If the archive is malformed or unsafe.
    """
    try:
        with zipfile.ZipFile(archive_path) as zf:
            members = zf.infolist()
            if len(members) > _MAX_FILES:
                raise ScanError(f"Archive has too many files (>{_MAX_FILES}).")

            dest_root = os.path.realpath(dest_dir)
            for member in members:
                if member.file_size > _MAX_FILE_BYTES:
                    raise ScanError(f"File '{member.filename}' exceeds size limit.")
                target = os.path.realpath(os.path.join(dest_dir, member.filename))
                if not target.startswith(dest_root + os.sep) and target != dest_root:
                    raise ScanError("Archive contains an unsafe path (traversal).")

            zf.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise ScanError("Uploaded file is not a valid zip archive.") from exc


def _scan_root(extract_dir: str) -> str:
    """Return the effective project root inside an extracted archive.

    If the archive contains a single top-level directory, use it as the root.

    Args:
        extract_dir: The extraction directory.

    Returns:
        The path to scan.
    """
    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    if len(entries) == 1:
        candidate = os.path.join(extract_dir, entries[0])
        if os.path.isdir(candidate):
            return candidate
    return extract_dir


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
    plan = get_plan(user.plan)

    if not skip_tier3 and not plan.tier3_enabled:
        raise ScanError(
            f"Tier 3 (deep AI analysis) is not available on the {plan.name} plan. "
            f"Upgrade to Pro to enable it."
        )

    with tempfile.TemporaryDirectory(prefix="vibesafe_scan_") as work_dir:
        _safe_extract(archive_path, work_dir)
        scan_root = _scan_root(work_dir)

        _log.info("Running SaaS scan for user %s on %s", user.id, project_name)
        report_str = run(
            scan_root,
            ScanOptions(output_format="json", skip_tier3=skip_tier3),
        )

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
